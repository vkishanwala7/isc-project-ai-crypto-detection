"""Common ingest: validate -> decode -> hash -> store -> Asset row."""
from __future__ import annotations

import io
from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image
from sqlalchemy.orm import Session

from app.db.models import Asset
from app.services.media import hashing, storage
from app.services.media.validation import MediaError, SniffedMedia, decode_image, sanitize_filename, validate_upload
from app.core.config import settings


@dataclass
class Ingested:
    data: bytes
    sniffed: SniffedMedia
    image: Image.Image | None
    asset: Asset
    video_meta: dict | None = None


def video_probe(path) -> dict:
    cap = cv2.VideoCapture(str(path))
    try:
        if not cap.isOpened():
            raise MediaError("The video could not be opened (unsupported codec or corrupt file).", "UNSUPPORTED_CODEC", 422)
        n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0)
        w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        ok, frame = cap.read()
        if not ok or frame is None:
            raise MediaError("No decodable video frames found.", "CORRUPT_MEDIA", 422)
        mid = None
        if n > 2:
            cap.set(cv2.CAP_PROP_POS_FRAMES, n // 2)
            ok2, f2 = cap.read()
            mid = f2 if ok2 else None
        poster = Image.fromarray(cv2.cvtColor(mid if mid is not None else frame, cv2.COLOR_BGR2RGB))
        duration = (n / fps) if (n > 0 and fps > 0) else None
        if duration and duration > settings.max_video_seconds:
            raise MediaError(f"Video is {duration:.0f}s long; the limit is {settings.max_video_seconds:.0f}s.", "VIDEO_TOO_LONG", 413)
        return {"frames": n, "fps": fps, "width": w, "height": h, "duration_s": duration, "poster": poster}
    finally:
        cap.release()


def ingest(db: Session, case_id: str, data: bytes, filename: str | None, role: str = "original",
           allow_video: bool = True) -> Ingested:
    sm = validate_upload(data, allow_video=allow_video)
    img = None
    vmeta = None
    stored = None
    if sm.media_type == "image":
        img = decode_image(data)
        stored = storage.save_bytes(data, sm.ext)
        ph = hashing.phash_hex(img)
        w, h, dur = img.size[0], img.size[1], None
    else:
        stored = storage.save_bytes(data, sm.ext)
        try:
            vmeta = video_probe(storage.path_for(stored))
        except MediaError:
            storage.delete(stored)
            raise
        ph = hashing.phash_hex(vmeta["poster"])
        w, h, dur = vmeta["width"], vmeta["height"], vmeta["duration_s"]
    asset = Asset(case_id=case_id, role=role, stored_name=stored, display_name=sanitize_filename(filename),
                  mime=sm.mime, size_bytes=len(data), sha256=hashing.sha256_hex(data), phash=ph,
                  width=w, height=h, duration_s=dur)
    db.add(asset)
    db.flush()
    return Ingested(data=data, sniffed=sm, image=img, asset=asset, video_meta=vmeta)


def add_derived_asset(db: Session, case_id: str, data: bytes, mime: str, ext: str, role: str, display_name: str,
                      image: Image.Image | None = None) -> Asset:
    stored = storage.save_bytes(data, ext)
    ph = None
    w = h = None
    if image is None and mime.startswith("image/"):
        try:
            image = Image.open(io.BytesIO(data)).convert("RGB")
        except Exception:
            image = None
    if image is not None:
        ph = hashing.phash_hex(image)
        w, h = image.size
    asset = Asset(case_id=case_id, role=role, stored_name=stored, display_name=display_name, mime=mime,
                  size_bytes=len(data), sha256=hashing.sha256_hex(data), phash=ph, width=w, height=h)
    db.add(asset)
    db.flush()
    return asset


_ = np  # numpy imported for cv2 interop
