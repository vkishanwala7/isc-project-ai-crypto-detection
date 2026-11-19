"""Provenance orchestration: combines the C2PA adapter (primary) and the Ed25519 detached
envelope (supplementary, educational) behind one interface."""
from __future__ import annotations

import json

from app.services.provenance import c2pa_adapter, ed25519_envelope

STATUS_TEXT = {
    "VALID_PROVENANCE": "Valid provenance — manifest, content binding and signature validate, and the signer is trusted under the current (local demo) trust policy.",
    "VALID_BUT_UNTRUSTED_SIGNER": "Cryptographically valid, but the signer certificate/key is not trusted by the current trust policy.",
    "TAMPERED_OR_INVALID": "Integrity verification failed — the manifest, signature or content binding does not validate for these exact bytes.",
    "NO_PROVENANCE_FOUND": "No supported provenance record was found. This says nothing by itself about whether the content is real or manipulated.",
    "UNSUPPORTED_OR_UNREADABLE": "The provenance of this file could not be assessed (unsupported format or unreadable structure).",
}

# precedence when combining C2PA + detached envelope into one headline status
_RANK = {"TAMPERED_OR_INVALID": 0, "VALID_PROVENANCE": 1, "VALID_BUT_UNTRUSTED_SIGNER": 2,
         "UNSUPPORTED_OR_UNREADABLE": 3, "NO_PROVENANCE_FOUND": 4}


def parse_detached(raw: bytes | None, filename: str | None) -> tuple[dict | None, bytes | None, str | None]:
    """Classify an optional detached credential: VERIFRAME JSON envelope or a C2PA sidecar (.c2pa)."""
    if not raw:
        return None, None, None
    if len(raw) > 5 * 1024 * 1024:
        return None, None, "Detached credential larger than 5 MB was ignored."
    stripped = raw.lstrip()
    if stripped[:1] == b"{":
        try:
            return json.loads(raw.decode("utf-8")), None, None
        except Exception:
            return {"type": "unparseable"}, None, "Detached file looked like JSON but could not be parsed."
    return None, raw, None  # treat as C2PA manifest store bytes (sidecar)


def verify_media(data: bytes, mime: str, envelope: dict | None = None, sidecar: bytes | None = None) -> dict:
    c2pa_res = c2pa_adapter.verify(data, mime, sidecar)
    env_res = ed25519_envelope.verify_envelope(data, envelope) if envelope is not None else None
    statuses = [c2pa_res["status"]] + ([env_res["status"]] if env_res else [])
    headline = min(statuses, key=lambda s: _RANK[s])
    return {
        "status": headline,
        "status_text": STATUS_TEXT[headline],
        "c2pa": c2pa_res,
        "detached": env_res,
        "signature_valid": next((r.get("signature_valid") for r in (c2pa_res, env_res) if r and r.get("manifest_found")), None),
        "signer_trusted": next((r.get("signer_trusted") for r in (c2pa_res, env_res) if r and r.get("manifest_found")), None),
        "interpretation_rule": "Missing provenance does not mean media is fake. A valid signature does not prove the depicted event is true.",
    }
