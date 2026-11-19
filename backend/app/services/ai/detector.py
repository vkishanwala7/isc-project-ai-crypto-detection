"""Deepfake/manipulation detector: face detection -> EfficientNet-B0 -> calibrated score.

If the checkpoint is missing the detector reports MODEL_UNAVAILABLE and never fabricates a score.
"""
from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from app.core.config import settings
from app.services.ai import faces as face_mod
from app.services.ai.metrics import aggregate_scores, verdict_for

logger = logging.getLogger("veriframe.ai")

CHECKPOINT_NAME = "veriframe_effb0_safl.pt"
AGGREGATION_RULE_IMAGE = "max over detected faces (an image is flagged if any face is flagged); per-face scores are reported"
AGGREGATION_RULE_VIDEO = "mean of per-frame scores over valid face-containing sampled frames (per-frame score = max over faces in that frame); median and max also reported"
INCONCLUSIVE_MARGIN = 0.10


@dataclass
class ModelInfo:
    available: bool
    reason: str | None
    name: str | None = None
    version: str | None = None
    architecture: str | None = None
    threshold: float | None = None
    temperature: float | None = None
    checkpoint_sha256: str | None = None
    meta: dict | None = None


class Detector:
    def __init__(self, checkpoint: Path | None = None):
        self.checkpoint = checkpoint or (settings.model_dir / CHECKPOINT_NAME)
        self._model = None
        self._info: ModelInfo | None = None
        self._lock = threading.RLock()

    # ---------------- model loading ----------------
    def info(self) -> ModelInfo:
        with self._lock:
            if self._info is None:
                self._load()
            return self._info

    def _load(self) -> None:
        if not self.checkpoint.exists():
            self._info = ModelInfo(False, f"Model weights unavailable: {self.checkpoint.name} not found in model_weights/. "
                                          "Run backend/scripts/prepare_dataset.py and train_model.py (see docs/AI_MODEL_CARD.md).")
            return
        try:
            import timm
            import torch

            if settings.torch_threads:
                torch.set_num_threads(settings.torch_threads)
            raw = self.checkpoint.read_bytes()
            sha = hashlib.sha256(raw).hexdigest()
            ckpt = torch.load(self.checkpoint, map_location="cpu", weights_only=True)
            meta = ckpt["meta"]
            model = timm.create_model("efficientnet_b0", pretrained=False, num_classes=1)
            model.load_state_dict(ckpt["state_dict"])
            model.eval()
            self._model = model
            self._mean = np.array(meta["mean"], dtype=np.float32).reshape(1, 1, 3)
            self._std = np.array(meta["std"], dtype=np.float32).reshape(1, 1, 3)
            self._info = ModelInfo(True, None, meta.get("model_name"), meta.get("version"), meta.get("architecture"),
                                   float(meta["threshold"]), float(meta["temperature"]), sha, meta)
            logger.info("Loaded detector %s (sha256 %s)", meta.get("model_name"), sha[:12])
        except Exception as e:  # pragma: no cover - defensive
            logger.exception("model load failed")
            self._info = ModelInfo(False, f"Model weights could not be loaded: {type(e).__name__}")

    # ---------------- inference ----------------
    def _score_crops(self, crops: list[Image.Image]) -> list[float]:
        import torch

        info = self.info()
        arr = np.stack([(np.asarray(c, dtype=np.float32) / 255.0 - self._mean) / self._std for c in crops])
        x = torch.from_numpy(arr.transpose(0, 3, 1, 2).copy())
        with torch.inference_mode():
            logits = self._model(x).squeeze(1).numpy()
        return [float(1 / (1 + np.exp(-lg / info.temperature))) for lg in logits]

    def _base(self, info: ModelInfo) -> dict:
        return {
            "model": {"name": info.name, "version": info.version, "architecture": info.architecture,
                      "checkpoint_sha256": info.checkpoint_sha256, "trained_by": "this project (VERIFRAME Team 16)"},
            "threshold": info.threshold,
            "inconclusive_band": [round(max(0.01, info.threshold - INCONCLUSIVE_MARGIN), 4), round(min(0.99, info.threshold + INCONCLUSIVE_MARGIN), 4)],
            "score_semantics": "Temperature-scaled model output in [0,1] (calibrated on the SAFL validation split). It is a model estimate of manipulation likelihood for faces resembling the training data, not a probability that the content is true or false.",
        }

    def unavailable_result(self, info: ModelInfo) -> dict:
        return {"status": "MODEL_UNAVAILABLE", "verdict": "INCONCLUSIVE", "reason": "MODEL_UNAVAILABLE",
                "score": None, "message": info.reason}

    def analyze_image(self, img: Image.Image) -> dict:
        info = self.info()
        if not info.available:
            return self.unavailable_result(info)
        t0 = time.time()
        detected = face_mod.detect_faces(img)
        base = self._base(info)
        if not detected:
            return {**base, "status": "COMPLETED", "verdict": "INCONCLUSIVE", "reason": "NO_FACE_DETECTED", "score": None,
                    "faces": [], "message": "No face was detected with sufficient confidence. The classifier is trained on face crops, so no score is produced.",
                    "duration_ms": int((time.time() - t0) * 1000)}
        scores = self._score_crops([f.crop for f in detected])
        agg = aggregate_scores(scores, "max")
        return {
            **base, "status": "COMPLETED", "verdict": verdict_for(agg, info.threshold, INCONCLUSIVE_MARGIN),
            "reason": None, "score": round(agg, 4), "aggregation": AGGREGATION_RULE_IMAGE,
            "faces": [{"box": f.box, "detector_confidence": round(f.prob, 4), "score": round(s, 4),
                       "verdict": verdict_for(s, info.threshold, INCONCLUSIVE_MARGIN)} for f, s in zip(detected, scores)],
            "image_size": list(img.size), "duration_ms": int((time.time() - t0) * 1000),
        }

    def analyze_video(self, path: Path) -> dict:
        import cv2

        info = self.info()
        if not info.available:
            return self.unavailable_result(info)
        t0 = time.time()
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            return {"status": "FAILED", "verdict": "INCONCLUSIVE", "reason": "UNSUPPORTED_CODEC", "score": None,
                    "message": "The video container/codec could not be opened."}
        try:
            n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            fps = float(cap.get(cv2.CAP_PROP_FPS) or 0)
            if n_frames <= 0 or fps <= 0:
                # some containers (e.g. browser WebM) lack frame counts: decode sequentially to count (bounded)
                frames_buf = []
                while len(frames_buf) < int(settings.max_video_seconds * 60):
                    ok, fr = cap.read()
                    if not ok:
                        break
                    frames_buf.append(fr)
                n_frames = len(frames_buf)
                fps = fps if fps > 0 else 30.0
            else:
                frames_buf = None
            duration = n_frames / fps if fps else 0
            if n_frames == 0:
                return {"status": "FAILED", "verdict": "INCONCLUSIVE", "reason": "CORRUPT_MEDIA", "score": None,
                        "message": "No decodable frames."}
            if duration > settings.max_video_seconds:
                return {"status": "FAILED", "verdict": "INCONCLUSIVE", "reason": "VIDEO_TOO_LONG", "score": None,
                        "message": f"Video is {duration:.0f}s; the limit is {settings.max_video_seconds:.0f}s."}
            k = min(settings.video_sample_frames, settings.video_sample_frames_cap, n_frames)
            idxs = sorted(set(np.linspace(0, n_frames - 1, k).round().astype(int).tolist()))
            frames = []
            for idx in idxs:
                if frames_buf is not None:
                    fr = frames_buf[idx]
                    ok = True
                else:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
                    ok, fr = cap.read()
                if not ok or fr is None:
                    frames.append({"index": idx, "timestamp_s": round(idx / fps, 3), "status": "UNREADABLE"})
                    continue
                img = Image.fromarray(cv2.cvtColor(fr, cv2.COLOR_BGR2RGB))
                detected = face_mod.detect_faces(img, max_faces=2)
                if not detected:
                    frames.append({"index": idx, "timestamp_s": round(idx / fps, 3), "status": "NO_FACE"})
                    continue
                s = self._score_crops([f.crop for f in detected])
                frames.append({"index": idx, "timestamp_s": round(idx / fps, 3), "status": "SCORED", "faces": len(detected),
                               "score": round(max(s), 4)})
        finally:
            cap.release()
        valid = [f["score"] for f in frames if f["status"] == "SCORED"]
        base = self._base(info)
        common = {"frames": frames, "frames_sampled": len(frames), "frames_with_faces": len(valid), "total_frames": n_frames,
                  "fps": round(fps, 2), "duration_s": round(duration, 2), "sampling": f"{len(frames)} frames sampled evenly across the clip (limit {settings.video_sample_frames}, hard cap {settings.video_sample_frames_cap})",
                  "scope_note": "Sampled-frame visual analysis only — not every frame, and audio is not analysed.",
                  "duration_ms": int((time.time() - t0) * 1000)}
        if not valid:
            return {**base, **common, "status": "COMPLETED", "verdict": "INCONCLUSIVE", "reason": "NO_FACE_DETECTED", "score": None,
                    "message": "No sampled frame contained a detectable face; no score is produced."}
        agg = aggregate_scores(valid, "mean")
        return {**base, **common, "status": "COMPLETED", "verdict": verdict_for(agg, info.threshold, INCONCLUSIVE_MARGIN),
                "reason": None, "score": round(agg, 4), "aggregation": AGGREGATION_RULE_VIDEO,
                "median_score": round(aggregate_scores(valid, "median"), 4), "max_score": round(max(valid), 4)}


_detector: Detector | None = None


def get_detector() -> Detector:
    global _detector
    if _detector is None:
        _detector = Detector()
    return _detector


def load_metrics() -> dict | None:
    p = settings.model_dir / "metrics.json"
    return json.loads(p.read_text()) if p.exists() else None


def load_training_log() -> dict | None:
    p = settings.model_dir / "training_log.json"
    return json.loads(p.read_text()) if p.exists() else None
