"""Face detection + cropping shared by training and inference.

Uses the MTCNN implementation from `facenet-pytorch` (MIT licence). Its P/R/O-Net
weights ship inside the PyPI wheel, so no network download is needed at runtime.
The exact same cropping function is used in `scripts/prepare_dataset.py` and at
inference time, so train/test preprocessing matches.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass

import numpy as np
from PIL import Image

DETECT_MAX_SIDE = 640      # images are downscaled to this size for detection only
MIN_FACE_PROB = 0.90       # MTCNN confidence required to accept a face
MIN_FACE_SIZE = 40         # px, in original image coordinates
CROP_MARGIN = 0.30         # extra context around the box (fraction of box size)
CROP_SIZE = 224            # classifier input size
MAX_FACES = 4              # faces classified per image/frame

_lock = threading.RLock()
_detector = None


def get_detector():
    global _detector
    with _lock:
        if _detector is None:
            from facenet_pytorch import MTCNN  # imported lazily (pulls in torch)

            _detector = MTCNN(keep_all=True, device="cpu", post_process=False, select_largest=False)
    return _detector


@dataclass
class FaceCrop:
    box: tuple[int, int, int, int]   # x1, y1, x2, y2 in original image pixels
    prob: float
    crop: Image.Image                # CROP_SIZE x CROP_SIZE RGB


def detect_faces(img: Image.Image, max_faces: int = MAX_FACES) -> list[FaceCrop]:
    """Return up to `max_faces` face crops, largest first."""
    img = img.convert("RGB")
    w, h = img.size
    scale = min(1.0, DETECT_MAX_SIDE / max(w, h))
    small = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.BILINEAR) if scale < 1 else img
    with _lock:
        boxes, probs = get_detector().detect(small)
    if boxes is None:
        return []
    faces: list[FaceCrop] = []
    for b, p in zip(boxes, probs):
        if p is None or p < MIN_FACE_PROB:
            continue
        x1, y1, x2, y2 = (float(v) / scale for v in b)
        bw, bh = x2 - x1, y2 - y1
        if min(bw, bh) < MIN_FACE_SIZE * min(1.0, max(w, h) / 400):
            continue
        # square crop with margin, clamped to the image
        side = max(bw, bh) * (1 + CROP_MARGIN)
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        sx1, sy1 = int(max(0, cx - side / 2)), int(max(0, cy - side / 2))
        sx2, sy2 = int(min(w, cx + side / 2)), int(min(h, cy + side / 2))
        if sx2 - sx1 < 8 or sy2 - sy1 < 8:
            continue
        crop = img.crop((sx1, sy1, sx2, sy2)).resize((CROP_SIZE, CROP_SIZE), Image.BICUBIC)
        faces.append(FaceCrop(box=(int(x1), int(y1), int(x2), int(y2)), prob=float(p), crop=crop))
    faces.sort(key=lambda f: (f.box[2] - f.box[0]) * (f.box[3] - f.box[1]), reverse=True)
    return faces[:max_faces]


def to_array(img: Image.Image) -> np.ndarray:
    return np.asarray(img.convert("RGB"), dtype=np.uint8)
