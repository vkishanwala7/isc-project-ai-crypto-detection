"""Server-side upload validation: size limits, magic-byte sniffing, safe decoding.
The client-supplied filename and Content-Type are never trusted."""
from __future__ import annotations

import io
import re
import unicodedata
from dataclasses import dataclass

from PIL import Image, ImageOps

from app.core.config import settings

Image.MAX_IMAGE_PIXELS = settings.max_image_pixels  # decompression-bomb guard


class MediaError(ValueError):
    def __init__(self, message: str, code: str = "INVALID_MEDIA", http_status: int = 415):
        super().__init__(message)
        self.code = code
        self.http_status = http_status


IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
VIDEO_TYPES = {"video/mp4": ".mp4", "video/quicktime": ".mov", "video/webm": ".webm"}
ACCEPTED = {**IMAGE_TYPES, **VIDEO_TYPES}


@dataclass
class SniffedMedia:
    mime: str
    ext: str
    media_type: str  # image | video


def sniff(data: bytes) -> SniffedMedia | None:
    """Identify the format from file signatures (magic bytes)."""
    h = data[:32]
    if h.startswith(b"\xff\xd8\xff"):
        mime = "image/jpeg"
    elif h.startswith(b"\x89PNG\r\n\x1a\n"):
        mime = "image/png"
    elif h[:4] == b"RIFF" and h[8:12] == b"WEBP":
        mime = "image/webp"
    elif h[4:8] == b"ftyp":
        brand = h[8:12]
        mime = "video/quicktime" if brand == b"qt  " else "video/mp4"
    elif h.startswith(b"\x1a\x45\xdf\xa3"):
        mime = "video/webm"
    else:
        return None
    return SniffedMedia(mime=mime, ext=ACCEPTED[mime], media_type="image" if mime in IMAGE_TYPES else "video")


def sanitize_filename(name: str | None, fallback: str = "upload") -> str:
    """Display-only filename: strip paths, control chars and markup-significant characters."""
    if not name:
        return fallback
    name = unicodedata.normalize("NFKC", name).replace("\\", "/").split("/")[-1]
    name = re.sub(r"[\x00-\x1f\x7f<>\"'`&;|$]", "", name).strip(" .")
    return (name[:120] or fallback)


def validate_upload(data: bytes, allow_video: bool = True) -> SniffedMedia:
    if not data:
        raise MediaError("The uploaded file is empty.", "EMPTY_FILE", 400)
    sm = sniff(data)
    if sm is None:
        raise MediaError("Unsupported or unrecognised file format. Accepted: JPEG, PNG, WebP images; MP4, MOV, WebM videos.",
                         "UNSUPPORTED_FORMAT")
    if sm.media_type == "video" and not allow_video:
        raise MediaError("This workflow accepts images only (JPEG, PNG, WebP).", "VIDEO_NOT_ALLOWED")
    limit = settings.max_image_bytes if sm.media_type == "image" else settings.max_video_bytes
    if len(data) > limit:
        raise MediaError(f"File too large: {len(data)/1e6:.1f} MB exceeds the {limit/1024/1024:.0f} MB {sm.media_type} limit.",
                         "FILE_TOO_LARGE", 413)
    return sm


def decode_image(data: bytes) -> Image.Image:
    """Fully decode an image (catches truncation / corruption / bombs). Applies EXIF orientation."""
    try:
        with Image.open(io.BytesIO(data)) as im:
            im.verify()
        im = Image.open(io.BytesIO(data))
        im.load()
        im = ImageOps.exif_transpose(im)
        return im.convert("RGB")
    except Image.DecompressionBombError as e:
        raise MediaError("Image dimensions exceed the safety limit.", "IMAGE_TOO_LARGE", 413) from e
    except Exception as e:
        raise MediaError("The image could not be decoded (corrupt or truncated file).", "CORRUPT_MEDIA", 422) from e
