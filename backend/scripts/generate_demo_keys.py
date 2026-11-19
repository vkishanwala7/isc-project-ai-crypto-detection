"""Generate (or rotate with --rotate) the development-only signing material in keys/.

  * VERIFRAME Local Demo Root CA + VERIFRAME Demo Signer certificate (ES256) for C2PA
  * Ed25519 key pair for the detached educational envelope

Rotating invalidates trust in assets signed with the previous keys (they will verify as
'valid but untrusted signer' or fail key pinning) - which is itself a useful demonstration.
Usage:  python backend/scripts/generate_demo_keys.py [--rotate]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings  # noqa: E402
from app.services.provenance.keys import generate_demo_keys, load_keys  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--rotate", action="store_true", help="overwrite existing keys")
a = ap.parse_args()
existed = (settings.keys_dir / "demo_signer.key").exists()
generate_demo_keys(settings.keys_dir, overwrite=a.rotate)
km = load_keys(reload=True)
print(("Rotated" if a.rotate and existed else "Existing keys kept" if existed else "Generated") + f" demo keys in {settings.keys_dir}")
print("  signer:", km.signer_summary()["subject"], "fingerprint", km.signer_summary()["sha256_fingerprint"][:16], "…")
print("  ed25519 key id:", km.ed_key_id)
