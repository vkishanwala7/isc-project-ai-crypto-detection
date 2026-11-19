"""AI pipeline tests: validation, preprocessing, no-face handling, model-unavailable state,
video frame-limit sampling, aggregation and threshold logic."""
from __future__ import annotations

import io
import tempfile
from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image

from conftest import make_jpeg

from app.core.config import settings
from app.services.ai import metrics
from app.services.ai.detector import Detector, get_detector
from app.services.media.validation import MediaError, decode_image, sanitize_filename, sniff, validate_upload

MODEL_PRESENT = (settings.model_dir / "veriframe_effb0_safl.pt").exists()
SAMPLES = Path(__file__).resolve().parents[2] / "data" / "samples" / "files"


def _face_image() -> Image.Image | None:
    if SAMPLES.exists():
        for name in ("TPNE0993.jpg", "RC000843.jpg", "FARC001055.jpg"):
            if (SAMPLES / name).exists():
                return Image.open(SAMPLES / name).convert("RGB")
    return None


def test_preprocessing_accepts_valid_image():
    data = make_jpeg()
    sm = validate_upload(data)
    assert sm.mime == "image/jpeg" and sm.media_type == "image"
    img = decode_image(data)
    assert img.mode == "RGB" and img.size == (320, 240)


def test_corrupt_media_clear_error():
    with pytest.raises(MediaError) as e:
        validate_upload(b"not an image at all")
    assert e.value.code == "UNSUPPORTED_FORMAT"
    with pytest.raises(MediaError) as e:
        decode_image(make_jpeg()[:500])
    assert e.value.code == "CORRUPT_MEDIA"


def test_magic_bytes_not_extension():
    assert sniff(b"\x89PNG\r\n\x1a\n" + b"\0" * 20).mime == "image/png"
    assert sniff(b"\0\0\0\x18ftypmp42" + b"\0" * 20).mime == "video/mp4"
    assert sniff(b"GIF89a....") is None


def test_filename_sanitised():
    assert sanitize_filename("../../etc/<script>passwd") == "scriptpasswd"
    assert "/" not in sanitize_filename("a/b\\c.jpg")


def test_model_unavailable_is_explicit():
    det = Detector(checkpoint=Path(tempfile.mkdtemp()) / "missing.pt")
    info = det.info()
    assert info.available is False and "unavailable" in info.reason.lower()
    r = det.analyze_image(Image.new("RGB", (64, 64)))
    assert r["status"] == "MODEL_UNAVAILABLE" and r["score"] is None


@pytest.mark.skipif(not MODEL_PRESENT, reason="trained checkpoint not present")
def test_no_face_returns_inconclusive():
    r = get_detector().analyze_image(Image.open(io.BytesIO(make_jpeg())).convert("RGB"))
    assert r["status"] == "COMPLETED"
    assert r["verdict"] == "INCONCLUSIVE" and r["reason"] == "NO_FACE_DETECTED" and r["score"] is None


@pytest.mark.skipif(not MODEL_PRESENT or _face_image() is None, reason="needs checkpoint and a fetched face sample")
def test_face_image_scored():
    r = get_detector().analyze_image(_face_image())
    assert r["status"] == "COMPLETED" and r["faces"]
    assert 0.0 <= r["score"] <= 1.0
    assert r["threshold"] is not None


@pytest.mark.skipif(not MODEL_PRESENT, reason="trained checkpoint not present")
def test_video_sampling_respects_limit(monkeypatch):
    p = Path(tempfile.mkdtemp()) / "clip.mp4"
    w = cv2.VideoWriter(str(p), cv2.VideoWriter_fourcc(*"mp4v"), 10, (96, 72))
    for i in range(60):
        w.write(np.full((72, 96, 3), (i * 4) % 255, np.uint8))
    w.release()
    monkeypatch.setattr(settings.__class__, "video_sample_frames", 7, raising=False)
    object.__setattr__(settings, "video_sample_frames", 7)
    try:
        r = get_detector().analyze_video(p)
    finally:
        object.__setattr__(settings, "video_sample_frames", 16)
    assert r["frames_sampled"] <= 7
    assert r["reason"] == "NO_FACE_DETECTED" and r["score"] is None  # flat frames have no faces


def test_aggregation_rules():
    assert metrics.aggregate_scores([0.2, 0.4, 0.9], "mean") == pytest.approx(0.5)
    assert metrics.aggregate_scores([0.2, 0.4, 0.9], "median") == pytest.approx(0.4)
    assert metrics.aggregate_scores([0.2, 0.4, 0.9], "max") == pytest.approx(0.9)
    assert metrics.aggregate_scores([], "mean") is None
    with pytest.raises(ValueError):
        metrics.aggregate_scores([0.1], "mode")


def test_threshold_and_inconclusive_band():
    assert metrics.verdict_for(0.9, 0.5) == "LIKELY_MANIPULATED"
    assert metrics.verdict_for(0.1, 0.5) == "LOW_MANIPULATION_SIGNAL"
    assert metrics.verdict_for(0.55, 0.5) == "INCONCLUSIVE"
    assert metrics.verdict_for(0.45, 0.5) == "INCONCLUSIVE"
    assert metrics.verdict_for(None, 0.5) == "INCONCLUSIVE"


def test_metrics_helpers():
    y = np.array([0, 0, 1, 1])
    s = np.array([0.1, 0.4, 0.35, 0.8])
    assert metrics.roc_auc(y, s) == pytest.approx(0.75)
    m = metrics.binary_metrics(y, s, 0.5)
    assert m["confusion_matrix"] == {"tn": 2, "fp": 0, "fn": 1, "tp": 1}
    assert 0 <= metrics.expected_calibration_error(y, s) <= 1
    assert metrics.fit_temperature(np.array([-3.0, 3.0, -2.0, 2.0]), np.array([0, 1, 0, 1])) < 1.0
