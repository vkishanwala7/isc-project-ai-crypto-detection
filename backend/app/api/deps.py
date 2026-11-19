from __future__ import annotations

from fastapi import HTTPException, UploadFile

from app.core.config import settings
from app.services.media.validation import MediaError


async def read_upload(upload: UploadFile | None, limit: int | None = None) -> bytes:
    """Read an upload with a hard byte cap (prevents unbounded memory use)."""
    if upload is None:
        raise HTTPException(400, detail={"code": "NO_FILE", "message": "No file was uploaded."})
    limit = limit or max(settings.max_image_bytes, settings.max_video_bytes)
    chunks, total = [], 0
    while True:
        chunk = await upload.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise HTTPException(413, detail={"code": "FILE_TOO_LARGE", "message": f"Upload exceeds the {limit // (1024*1024)} MB limit."})
        chunks.append(chunk)
    return b"".join(chunks)


def media_http_error(e: MediaError) -> HTTPException:
    return HTTPException(e.http_status, detail={"code": e.code, "message": str(e)})
