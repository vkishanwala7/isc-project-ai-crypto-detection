"""Supplementary educational proof: a detached Ed25519 signature envelope.

    VERIFRAME detached-signature demo — not a C2PA Content Credential.

envelope = {
  "type": "veriframe.detached-signature.v1",
  "claim": {... "asset": {"sha256": <hex of exact bytes>, "size": n, "mime": ...}, ...},
  "signature": {"alg": "Ed25519", "key_id": ..., "public_key_b64": ..., "value_b64": sign(canonical(claim))}
}

canonical(claim) = JSON with sorted keys, no insignificant whitespace, UTF-8 (RFC 8785-style subset;
the claim only contains strings/ints/bools so number canonicalisation is not an issue).
"""
from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timezone

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from app.core.config import settings
from app.services.provenance.keys import load_keys

ENVELOPE_TYPE = "veriframe.detached-signature.v1"
LABEL = "VERIFRAME detached-signature demo — not a C2PA Content Credential"


def canonical_json(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def create_envelope(data: bytes, mime: str, *, case_id: str, source: str, note: str) -> dict:
    km = load_keys()
    claim = {
        "asset": {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data), "mime": mime},
        "issued_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "issuer": "VERIFRAME demo service",
        "source": source,
        "note": note,
        "case_id": case_id,
        "generator": f"VERIFRAME {settings.app_version}",
    }
    sig = km.ed_private.sign(canonical_json(claim))
    return {
        "type": ENVELOPE_TYPE,
        "label": LABEL,
        "claim": claim,
        "signature": {
            "alg": "Ed25519",
            "key_id": km.ed_key_id,
            "public_key_b64": base64.b64encode(km.ed_public_raw).decode(),
            "value_b64": base64.b64encode(sig).decode(),
            "signed_bytes": "canonical_json(claim): sorted keys, compact separators, UTF-8",
        },
    }


def verify_envelope(data: bytes, envelope: dict) -> dict:
    """Independently verify (1) the signature over the canonical claim and (2) the digest binding."""
    km = load_keys()
    out = {"implementation": LABEL, "steps": []}
    try:
        if envelope.get("type") != ENVELOPE_TYPE:
            raise ValueError("not a VERIFRAME detached-signature envelope")
        claim = envelope["claim"]
        sig = envelope["signature"]
        pub_raw = base64.b64decode(sig["public_key_b64"], validate=True)
        value = base64.b64decode(sig["value_b64"], validate=True)
        expected_digest = str(claim["asset"]["sha256"]).lower()
    except Exception as e:
        return {**out, "status": "UNSUPPORTED_OR_UNREADABLE", "error": f"Malformed envelope: {str(e)[:160]}",
                "steps": [{"key": "discovery", "label": "Envelope parsing", "state": "fail", "detail": "The detached envelope is malformed or of an unknown type."}]}

    try:
        Ed25519PublicKey.from_public_bytes(pub_raw).verify(value, canonical_json(claim))
        sig_ok = True
    except (InvalidSignature, ValueError):
        sig_ok = False
    actual = hashlib.sha256(data).hexdigest()
    binding_ok = actual == expected_digest
    trusted = pub_raw == km.ed_public_raw  # local trust policy: the service's own published key

    status = "TAMPERED_OR_INVALID" if not (sig_ok and binding_ok) else ("VALID_PROVENANCE" if trusted else "VALID_BUT_UNTRUSTED_SIGNER")
    out.update({
        "status": status, "manifest_found": True, "signature_valid": sig_ok, "binding_valid": binding_ok,
        "signer_trusted": trusted, "key_id": sig.get("key_id"), "expected_sha256": expected_digest, "actual_sha256": actual,
        "claim": claim,
        "trust_policy": "VERIFRAME local key pinning (the service's own Ed25519 public key)",
        "steps": [
            {"key": "discovery", "label": "Envelope parsing", "state": "pass", "detail": f"{ENVELOPE_TYPE}, key {sig.get('key_id')}"},
            {"key": "binding", "label": "Digest binding (SHA-256 of exact bytes)", "state": "pass" if binding_ok else "fail",
             "detail": ("SHA-256 of the uploaded file equals the digest in the signed claim." if binding_ok
                        else f"Digest mismatch: claim expects {expected_digest[:16]}…, file is {actual[:16]}…")},
            {"key": "signature", "label": "Ed25519 signature over canonical claim", "state": "pass" if sig_ok else "fail",
             "detail": "Signature verifies with the embedded public key." if sig_ok else "Signature does NOT verify: the claim was altered or signed by another key."},
            {"key": "trust", "label": "Key trust (local pinning)", "state": "pass" if trusted else "warn",
             "detail": "Public key matches this VERIFRAME instance's demo key." if trusted else "Public key is not the pinned VERIFRAME demo key."},
        ],
    })
    return out
