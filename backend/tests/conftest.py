"""Test configuration: every test session uses an isolated temporary data/keys directory."""
from __future__ import annotations

import io
import os
import sys
import tempfile
from pathlib import Path

_tmp = Path(tempfile.mkdtemp(prefix="veriframe-test-"))
os.environ["VERIFRAME_DATA_DIR"] = str(_tmp)
os.environ["VERIFRAME_STORAGE_DIR"] = str(_tmp / "storage")
os.environ["VERIFRAME_DB_PATH"] = str(_tmp / "test.db")
os.environ["VERIFRAME_KEYS_DIR"] = str(_tmp / "keys")
os.environ.setdefault("VERIFRAME_SAMPLES_DIR", str(_tmp / "samples"))
# Use the real trained checkpoint when present (repo model_weights/); tests that need the
# "unavailable" state construct their own Detector pointing at a missing file.
os.environ.setdefault("VERIFRAME_MODEL_DIR", str(Path(__file__).resolve().parents[2] / "model_weights"))

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402


def make_jpeg(w: int = 320, h: int = 240, seed: int = 0) -> bytes:
    img = Image.new("RGB", (w, h), (20 + seed, 60, 120))
    d = ImageDraw.Draw(img)
    for i in range(8):
        d.rectangle((10 + i * 30, 20 + (i * 17 + seed) % 150, 40 + i * 30, 80 + (i * 17) % 150), fill=(200, 40 + i * 20, 90))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=90)
    return buf.getvalue()


def make_png(w: int = 200, h: int = 160) -> bytes:
    img = Image.new("RGB", (w, h), (240, 240, 240))
    ImageDraw.Draw(img).ellipse((40, 30, 160, 130), fill=(10, 140, 150))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def jpeg() -> bytes:
    return make_jpeg()


@pytest.fixture
def png() -> bytes:
    return make_png()


FACE_SAMPLE = Path(__file__).resolve().parents[2] / "data" / "samples" / "files"
