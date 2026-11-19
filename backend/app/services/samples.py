"""Demo Workspace samples.

`data/samples/samples.json` lists each sample, its documented label and its source/licence.
Dataset media are NOT redistributed with this project: `scripts/fetch_demo_samples.py` fetches
them from the official SAFL GitHub repository (pinned commit) and checks SHA-256 digests.
Samples are analysed as clearly-flagged sample cases (is_sample=True) and excluded from
dashboard statistics by default."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from app.core.config import settings


def _manifest() -> list[dict]:
    p = settings.samples_dir / "samples.json"
    if not p.exists():
        return []
    return json.loads(p.read_text()).get("samples", [])


def _file(s: dict) -> Path:
    p = (settings.samples_dir / "files" / s["filename"]).resolve()
    if p.parent != (settings.samples_dir / "files").resolve():
        raise ValueError("bad sample path")
    return p


def list_samples() -> dict:
    out = []
    for s in _manifest():
        p = _file(s)
        present = p.exists() and hashlib.sha256(p.read_bytes()).hexdigest() == s["sha256"]
        out.append({k: s[k] for k in ("id", "filename", "media_type", "label", "label_text", "source", "license", "used_for_training", "note") if k in s}
                   | {"available": present})
    return {"samples": out, "fetch_command": "python scripts/fetch_demo_samples.py",
            "note": "Labels come from the source dataset/fixture documentation. Model outputs are shown as produced, including errors."}


def load_sample(sample_id: str) -> tuple[dict, bytes] | None:
    for s in _manifest():
        if s["id"] == sample_id:
            p = _file(s)
            if not p.exists():
                return None
            data = p.read_bytes()
            if hashlib.sha256(data).hexdigest() != s["sha256"]:
                return None
            return s, data
    return None
