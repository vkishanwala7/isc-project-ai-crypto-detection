"""Cryptography tests: SHA-256, C2PA sign/verify, Ed25519 envelope, trust vs validity, pHash separation."""
from __future__ import annotations

import base64
import copy
import json

from conftest import make_jpeg

from app.services.media import hashing
from app.services.provenance import c2pa_adapter, ed25519_envelope, tamper
from app.services.provenance.keys import load_keys
from app.services.provenance.service import parse_detached, verify_media


def test_sha256_deterministic():
    data = make_jpeg()
    assert hashing.sha256_hex(data) == hashing.sha256_hex(bytes(data))


def test_one_byte_change_changes_sha256():
    data = bytearray(make_jpeg())
    before = hashing.sha256_hex(bytes(data))
    data[len(data) // 2] ^= 0x01
    after = hashing.sha256_hex(bytes(data))
    assert before != after
    # avalanche: a substantial fraction of the 256 bits flip
    assert bin(int(before, 16) ^ int(after, 16)).count("1") > 64


def test_c2pa_sign_and_verify_valid_trusted():
    signed, manifest = c2pa_adapter.sign(make_jpeg(), "image/jpeg", "t.jpg", workflow="upload", software_agent="test", description="d")
    r = c2pa_adapter.verify(signed, "image/jpeg")
    assert r["status"] == "VALID_PROVENANCE"
    assert r["signature_valid"] is True and r["binding_valid"] is True and r["signer_trusted"] is True
    assert r["signer"]["common_name"] == "VERIFRAME Demo Signer"
    assert any(a["action"] == "c2pa.opened" for a in r["actions"])


def test_c2pa_capture_uses_created_digital_capture():
    signed, _ = c2pa_adapter.sign(make_jpeg(), "image/jpeg", "c.jpg", workflow="capture", software_agent="test", description="d")
    r = c2pa_adapter.verify(signed, "image/jpeg")
    assert r["status"] == "VALID_PROVENANCE"
    assert r["actions"][0]["action"] == "c2pa.created"
    assert r["actions"][0]["digitalSourceType"].endswith("digitalCapture")
    assert r["signing_context"]["hardware_attestation"] is False


def test_c2pa_tampered_bytes_fail_binding():
    signed, _ = c2pa_adapter.sign(make_jpeg(), "image/jpeg", "t.jpg", workflow="upload", software_agent="t", description="d")
    tampered, _ = tamper.tamper_jpeg_quant_table(signed)
    assert len(tampered) == len(signed) and tampered != signed
    r = c2pa_adapter.verify(tampered, "image/jpeg")
    assert r["status"] == "TAMPERED_OR_INVALID"
    assert r["binding_valid"] is False
    assert any("dataHash" in f["code"] for f in r["validation_codes"]["failure"])


def test_png_tamper_detected(png):
    signed, _ = c2pa_adapter.sign(png, "image/png", "p.png", workflow="upload", software_agent="t", description="d")
    assert c2pa_adapter.verify(signed, "image/png")["status"] == "VALID_PROVENANCE"
    tampered, _ = tamper.tamper_png_pixel(signed)
    assert c2pa_adapter.verify(tampered, "image/png")["status"] == "TAMPERED_OR_INVALID"


def test_missing_manifest_is_not_fake():
    r = verify_media(make_jpeg(), "image/jpeg")
    assert r["status"] == "NO_PROVENANCE_FOUND"
    assert "fake" not in r["status_text"].lower().replace("real or fake", "")
    assert "says nothing" in r["status_text"]


def test_trust_state_distinct_from_signature_validity(monkeypatch):
    signed, _ = c2pa_adapter.sign(make_jpeg(), "image/jpeg", "t.jpg", workflow="upload", software_agent="t", description="d")
    # Verify with an empty trust policy: signature is still valid, signer untrusted.
    real_ctx = c2pa_adapter._context
    monkeypatch.setattr(c2pa_adapter, "_context", lambda with_trust: real_ctx(False))
    r = c2pa_adapter.verify(signed, "image/jpeg")
    assert r["status"] == "VALID_BUT_UNTRUSTED_SIGNER"
    assert r["signature_valid"] is True and r["signer_trusted"] is False


def test_malformed_manifest_handled_safely():
    signed, _ = c2pa_adapter.sign(make_jpeg(), "image/jpeg", "t.jpg", workflow="upload", software_agent="t", description="d")
    # corrupt bytes inside the embedded JUMBF (APP11 segment sits near the start)
    b = bytearray(signed)
    idx = signed.find(b"jumb")
    assert idx > 0
    for k in range(idx + 40, idx + 80):
        b[k] ^= 0xFF
    r = c2pa_adapter.verify(bytes(b), "image/jpeg")
    assert r["status"] in ("TAMPERED_OR_INVALID", "UNSUPPORTED_OR_UNREADABLE")
    assert "steps" in r


def test_ed25519_envelope_roundtrip_and_failures():
    data = make_jpeg(seed=3)
    env = ed25519_envelope.create_envelope(data, "image/jpeg", case_id="x", source="test", note="")
    ok = ed25519_envelope.verify_envelope(data, env)
    assert ok["status"] == "VALID_PROVENANCE" and ok["signature_valid"] and ok["binding_valid"]

    # changed media -> digest binding fails, signature still valid
    other = make_jpeg(seed=4)
    r = ed25519_envelope.verify_envelope(other, env)
    assert r["status"] == "TAMPERED_OR_INVALID" and r["binding_valid"] is False and r["signature_valid"] is True

    # changed claim -> signature fails
    forged = copy.deepcopy(env)
    forged["claim"]["source"] = "forged"
    r = ed25519_envelope.verify_envelope(data, forged)
    assert r["status"] == "TAMPERED_OR_INVALID" and r["signature_valid"] is False

    # attacker re-signs with their own key -> valid but untrusted signer
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    k = Ed25519PrivateKey.generate()
    rogue = copy.deepcopy(env)
    rogue["signature"]["public_key_b64"] = base64.b64encode(k.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()
    rogue["signature"]["value_b64"] = base64.b64encode(k.sign(ed25519_envelope.canonical_json(rogue["claim"]))).decode()
    r = ed25519_envelope.verify_envelope(data, rogue)
    assert r["status"] == "VALID_BUT_UNTRUSTED_SIGNER" and r["signature_valid"] and r["signer_trusted"] is False


def test_malformed_envelope_safe():
    r = ed25519_envelope.verify_envelope(make_jpeg(), {"type": "nope"})
    assert r["status"] == "UNSUPPORTED_OR_UNREADABLE"
    env, sidecar, warn = parse_detached(b"{not json", "x.json")
    assert warn and env == {"type": "unparseable"}
    r = verify_media(make_jpeg(), "image/jpeg", envelope=env)
    assert r["detached"]["status"] == "UNSUPPORTED_OR_UNREADABLE"


def test_phash_is_not_integrity_decision():
    """A re-encoded copy is visually near-identical by pHash, yet integrity verification fails."""
    signed, _ = c2pa_adapter.sign(make_jpeg(), "image/jpeg", "t.jpg", workflow="upload", software_agent="t", description="d")
    env = ed25519_envelope.create_envelope(signed, "image/jpeg", case_id="x", source="t", note="")
    edited, _ = tamper.visual_edit_reencode(signed)
    from PIL import Image
    import io
    d = hashing.phash_distance(hashing.phash_hex(Image.open(io.BytesIO(signed))), hashing.phash_hex(Image.open(io.BytesIO(edited))))
    assert d <= 10  # perceptually similar
    r = verify_media(edited, "image/jpeg", envelope=env)
    assert r["c2pa"]["status"] == "NO_PROVENANCE_FOUND"  # manifest stripped
    assert r["detached"]["status"] == "TAMPERED_OR_INVALID"
    assert r["status"] == "TAMPERED_OR_INVALID"  # the integrity decision ignores pHash entirely


def test_private_keys_never_in_public_material(client):
    km = load_keys()
    for path in ("/api/config", "/api/keys/public", "/api/health"):
        body = client.get(path).content
        assert b"PRIVATE KEY" not in body
        assert km.signer_key_pem.split(b"\n")[1] not in body


def test_key_files_permissions():
    import os
    from app.core.config import settings
    for name in ("demo_signer.key", "ed25519_private.pem", "demo_root_ca.key"):
        mode = os.stat(settings.keys_dir / name).st_mode & 0o777
        assert mode == 0o600, (name, oct(mode))


def test_mp4_sign_verify_tamper():
    from pathlib import Path
    import cv2, numpy as np, tempfile
    p = Path(tempfile.mkdtemp()) / "v.mp4"
    w = cv2.VideoWriter(str(p), cv2.VideoWriter_fourcc(*"mp4v"), 10, (64, 48))
    for i in range(10):
        w.write(np.full((48, 64, 3), i * 20, np.uint8))
    w.release()
    data = p.read_bytes()
    signed, _ = c2pa_adapter.sign(data, "video/mp4", "v.mp4", workflow="upload", software_agent="t", description="d")
    assert c2pa_adapter.verify(signed, "video/mp4")["status"] == "VALID_PROVENANCE"
    b = bytearray(signed)
    b[len(b) // 2] ^= 1
    assert c2pa_adapter.verify(bytes(b), "video/mp4")["status"] == "TAMPERED_OR_INVALID"
    _ = json  # keep import
