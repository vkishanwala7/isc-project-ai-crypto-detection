"""Central configuration. Values can be overridden with environment variables
(see .env.example at the repository root)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_dotenv() -> None:
    """Minimal .env loader (no extra dependency). Existing env vars win."""
    env_file = REPO_ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()


def _path(env: str, default: Path) -> Path:
    raw = os.environ.get(env)
    if not raw:
        return default
    p = Path(raw)
    return p if p.is_absolute() else (REPO_ROOT / p)


@dataclass(frozen=True)
class Settings:
    app_name: str = "VERIFRAME"
    app_version: str = "1.0.0"
    data_dir: Path = field(default_factory=lambda: _path("VERIFRAME_DATA_DIR", REPO_ROOT / "data"))
    storage_dir: Path = field(default_factory=lambda: _path("VERIFRAME_STORAGE_DIR", REPO_ROOT / "data" / "storage"))
    db_path: Path = field(default_factory=lambda: _path("VERIFRAME_DB_PATH", REPO_ROOT / "data" / "veriframe.db"))
    keys_dir: Path = field(default_factory=lambda: _path("VERIFRAME_KEYS_DIR", REPO_ROOT / "keys"))
    model_dir: Path = field(default_factory=lambda: _path("VERIFRAME_MODEL_DIR", REPO_ROOT / "model_weights"))
    samples_dir: Path = field(default_factory=lambda: _path("VERIFRAME_SAMPLES_DIR", REPO_ROOT / "data" / "samples"))
    max_image_bytes: int = int(os.environ.get("VERIFRAME_MAX_IMAGE_MB", "15")) * 1024 * 1024
    max_video_bytes: int = int(os.environ.get("VERIFRAME_MAX_VIDEO_MB", "60")) * 1024 * 1024
    max_image_pixels: int = int(os.environ.get("VERIFRAME_MAX_IMAGE_PIXELS", str(40_000_000)))
    max_video_seconds: float = float(os.environ.get("VERIFRAME_MAX_VIDEO_SECONDS", "120"))
    video_sample_frames: int = int(os.environ.get("VERIFRAME_VIDEO_SAMPLE_FRAMES", "16"))
    video_sample_frames_cap: int = 24
    cors_origins: tuple[str, ...] = tuple(
        o.strip() for o in os.environ.get(
            "VERIFRAME_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
        ).split(",") if o.strip()
    )
    # Optional extra trust anchors (PEM bundle) appended to the local demo root.
    extra_trust_anchors: Path | None = field(
        default_factory=lambda: _path("VERIFRAME_EXTRA_TRUST_ANCHORS", Path("")) if os.environ.get("VERIFRAME_EXTRA_TRUST_ANCHORS") else None
    )
    torch_threads: int = int(os.environ.get("VERIFRAME_TORCH_THREADS", "0"))


settings = Settings()

for _d in (settings.storage_dir, settings.keys_dir, settings.data_dir):
    _d.mkdir(parents=True, exist_ok=True)
