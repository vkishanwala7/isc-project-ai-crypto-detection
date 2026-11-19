"""File storage under generated names outside any public static directory.

User filenames are never used as filesystem paths. Files are only served through
`/api/files/{asset_id}` after a database lookup."""
from __future__ import annotations

import os
import uuid
from pathlib import Path

from app.core.config import settings


def save_bytes(data: bytes, ext: str) -> str:
    if not ext.startswith(".") or "/" in ext or len(ext) > 8:
        raise ValueError("bad extension")
    name = f"{uuid.uuid4().hex}{ext}"
    path = settings.storage_dir / name
    with open(path, "xb") as fh:
        fh.write(data)
    os.chmod(path, 0o640)
    return name


def path_for(stored_name: str) -> Path:
    p = (settings.storage_dir / stored_name).resolve()
    if p.parent != settings.storage_dir.resolve():
        raise ValueError("invalid stored name")
    return p


def read_bytes(stored_name: str) -> bytes:
    return path_for(stored_name).read_bytes()


def delete(stored_name: str) -> None:
    try:
        path_for(stored_name).unlink()
    except FileNotFoundError:
        pass
