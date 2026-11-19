"""Download the Demo Workspace samples listed in data/samples/samples.json from their official
sources (SAFL GitHub repository at a pinned commit; c2pa-python test fixtures) and verify SHA-256.

Usage:  python scripts/fetch_demo_samples.py
"""
from __future__ import annotations

import hashlib
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "samples" / "samples.json"
DEST = ROOT / "data" / "samples" / "files"


def main() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    samples = json.loads(MANIFEST.read_text())["samples"]
    failures = 0
    for s in samples:
        target = DEST / s["filename"]
        if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() == s["sha256"]:
            print(f"ok      {s['filename']} (already present)")
            continue
        try:
            with urllib.request.urlopen(s["url"], timeout=60) as r:
                data = r.read(80 * 1024 * 1024)
        except Exception as e:  # network/proxy issues
            print(f"FAILED  {s['filename']}: {e}")
            failures += 1
            continue
        digest = hashlib.sha256(data).hexdigest()
        if digest != s["sha256"]:
            print(f"FAILED  {s['filename']}: sha256 mismatch ({digest[:16]}…), file not saved")
            failures += 1
            continue
        target.write_bytes(data)
        print(f"fetched {s['filename']} ({len(data)/1024:.0f} KB, sha256 verified)")
    print("done" if not failures else f"{failures} sample(s) could not be fetched")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
