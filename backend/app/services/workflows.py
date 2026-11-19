"""Business workflows shared by API routes (analyze / sign / verify / integrity lab)."""
from __future__ import annotations

import io
import time
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter
from sqlalchemy.orm import Session

from app.db.models import Analysis, Asset, Case, ProvenanceRecord
from app.services import evidence
from app.services.ai.detector import get_detector
from app.services.audit.log import record
from app.services.media import hashing, storage
from app.services.media.ingest import Ingested, add_derived_asset, ingest
from app.services.provenance import c2pa_adapter, ed25519_envelope, tamper
from app.services.provenance.service import verify_media

def _ext_for(mime: str) -> str:
    return {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "video/mp4": ".mp4",
            "video/quicktime": ".mov", "video/webm": ".webm", "application/json": ".json"}[mime]


def _stem(name: str) -> str:
    return name.rsplit(".", 1)[0] if "." in name else name


def run_ai(db: Session, case: Case, ing: Ingested) -> dict:
    det = get_detector()
    t0 = time.time()
    try:
        if ing.sniffed.media_type == "image":
            res = det.analyze_image(ing.image)
        else:
            res = det.analyze_video(storage.path_for(ing.asset.stored_name))
    except Exception as e:  # pragma: no cover - defensive
        res = {"status": "FAILED", "verdict": "INCONCLUSIVE", "reason": "ANALYSIS_ERROR", "score": None,
               "message": f"Analysis failed safely: {type(e).__name__}"}
        record(db, "error", "ANALYSIS_ERROR", case.id, {"stage": "ai", "error": type(e).__name__}, commit=False)
    info = det.info()
    a = Analysis(case_id=case.id, asset_id=ing.asset.id, status=res["status"], verdict=res.get("verdict", "INCONCLUSIVE"),
                 reason=res.get("reason"), score=res.get("score"), threshold=res.get("threshold"),
                 model_name=info.name, model_version=info.version, details=res,
                 duration_ms=int((time.time() - t0) * 1000))
    db.add(a)
    record(db, "analysis", res.get("verdict") if res["status"] == "COMPLETED" else res["status"], case.id,
           {"score": res.get("score"), "reason": res.get("reason"), "model": info.name, "media_type": ing.sniffed.media_type}, commit=False)
    return res


def run_verify(db: Session, case: Case, asset: Asset, data: bytes, envelope: dict | None = None,
               sidecar: bytes | None = None, label: str = "verify") -> dict:
    res = verify_media(data, asset.mime, envelope, sidecar)
    res["similar_known_asset"] = nearest_known_asset(db, asset)
    signer = None
    c = res.get("c2pa") or {}
    if c.get("manifest_found") and c.get("signer"):
        signer = c["signer"].get("common_name")
    elif res.get("detached") and res["detached"].get("key_id"):
        signer = res["detached"]["key_id"]
    db.add(ProvenanceRecord(case_id=case.id, asset_id=asset.id, operation="verify", status=res["status"],
                            signature_valid=res.get("signature_valid"), signer_trusted=res.get("signer_trusted"),
                            signer=signer, details={**res, "label": label}))
    record(db, "verify", res["status"], case.id, {"asset_role": asset.role, "sha256": asset.sha256, "label": label,
                                                   "detached_supplied": envelope is not None or sidecar is not None}, commit=False)
    return res


def nearest_known_asset(db: Session, asset: Asset) -> dict | None:
    """pHash nearest neighbour among previously stored assets (similarity heuristic only)."""
    if not asset.phash:
        return None
    best = None
    rows = db.query(Asset.id, Asset.case_id, Asset.phash, Asset.sha256, Asset.role, Asset.display_name) \
        .filter(Asset.phash.isnot(None), Asset.case_id != asset.case_id).order_by(Asset.created_at.desc()).limit(2000).all()
    for r in rows:
        d = hashing.phash_distance(asset.phash, r.phash)
        if best is None or d < best["distance"]:
            best = {"distance": d, "case_id": r.case_id, "asset_role": r.role, "display_name": r.display_name,
                    "exact_byte_match": r.sha256 == asset.sha256}
    if best is None or best["distance"] > 20:
        return {"found": False, "note": "No visually similar asset among stored records (pHash heuristic)."}
    best["found"] = True
    best["label"] = hashing.similarity_label(best["distance"])
    best["note"] = "Perceptual similarity estimate only — not proof of identity, integrity or authenticity."
    return best


def analyze(db: Session, data: bytes, filename: str | None, *, sample: dict | None = None) -> Case:
    case = Case(kind="analysis", title="pending", media_type="image")
    db.add(case)
    db.flush()
    ing = ingest(db, case.id, data, filename)
    case.title = ing.asset.display_name
    case.media_type = ing.sniffed.media_type
    if sample:
        case.is_sample, case.sample_label, case.sample_source = True, sample["label"], sample["source"]
    record(db, "upload", "ACCEPTED", case.id, {"mime": ing.sniffed.mime, "size_bytes": len(data), "sha256": ing.asset.sha256,
                                               "sample": bool(sample)}, commit=False)
    ai = run_ai(db, case, ing)
    prov = run_verify(db, case, ing.asset, data, label="embedded provenance inspection")
    case.summary = evidence.interpret(ai, prov["status"])
    db.commit()
    return case


def sign(db: Session, data: bytes, filename: str | None, source: str, note: str = "") -> Case:
    case = Case(kind="signing", title="pending", media_type="image")
    db.add(case)
    db.flush()
    ing = ingest(db, case.id, data, filename)
    case.title = ing.asset.display_name
    case.media_type = ing.sniffed.media_type
    mime = ing.sniffed.mime
    record(db, "upload", "ACCEPTED", case.id, {"mime": mime, "size_bytes": len(data), "sha256": ing.asset.sha256, "source": source}, commit=False)

    is_capture = source == "browser_capture"
    description = ("Captured in the browser (getUserMedia/MediaRecorder) and signed by this VERIFRAME demo service after upload. "
                   "No hardware attestation, secure sensor pipeline or camera-manufacturer identity is asserted."
                   if is_capture else
                   "Uploaded to VERIFRAME and signed by the demo service. The signer attests only that it received these exact bytes at this time; "
                   "it makes no claim about how or by whom the content was originally created.")
    c2pa_info: dict = {"applied": False}
    signed_bytes = data
    signed_asset = ing.asset
    if mime in c2pa_adapter.C2PA_SIGN_MIMES:
        try:
            signed_bytes, manifest = c2pa_adapter.sign(
                data, mime, ing.asset.display_name, workflow="capture" if is_capture else "upload",
                software_agent="VERIFRAME browser capture workflow" if is_capture else "VERIFRAME upload & sign workflow",
                description=description, extra={"note": note[:200]} if note else None)
            signed_asset = add_derived_asset(db, case.id, signed_bytes, mime, _ext_for(mime), "signed",
                                             f"{_stem(ing.asset.display_name)}_signed{_ext_for(mime)}")
            c2pa_info = {"applied": True, "manifest_definition": manifest, "embedded": True}
        except Exception as e:
            c2pa_info = {"applied": False, "error": f"C2PA signing failed: {type(e).__name__}: {str(e)[:200]}"}
            record(db, "error", "C2PA_SIGN_FAILED", case.id, {"error": type(e).__name__}, commit=False)
    else:
        c2pa_info = {"applied": False, "reason": f"C2PA embedding is not supported for {mime} by the installed SDK; "
                                                 "only the detached Ed25519 educational envelope was produced."}

    env = ed25519_envelope.create_envelope(signed_bytes, mime, case_id=case.id, source=source, note=note[:200])
    import json as _json
    env_bytes = _json.dumps(env, indent=2).encode()
    env_asset = add_derived_asset(db, case.id, env_bytes, "application/json", ".json", "envelope",
                                  f"{_stem(ing.asset.display_name)}.veriframe-sig.json")

    # Re-open and verify through the verifier path (do not trust the signing return value)
    post = verify_media(signed_bytes, mime, env)
    km_signer = None
    from app.services.provenance.keys import load_keys
    km_signer = load_keys().signer_summary()
    db.add(ProvenanceRecord(case_id=case.id, asset_id=signed_asset.id, operation="sign", status=post["status"],
                            signature_valid=post.get("signature_valid"), signer_trusted=post.get("signer_trusted"),
                            signer=km_signer["subject"], details={
                                "source": source, "c2pa": c2pa_info, "envelope_asset_id": env_asset.id,
                                "signer_certificate": km_signer, "ed25519_key_id": env["signature"]["key_id"],
                                "original_sha256": ing.asset.sha256, "signed_sha256": signed_asset.sha256,
                                "post_sign_verification": post, "capture_statement": (
                                    "Signed by this VERIFRAME demo service after browser capture." if is_capture else
                                    "Signed by this VERIFRAME demo service after upload."),
                            }))
    record(db, "sign", post["status"], case.id, {"c2pa_applied": c2pa_info.get("applied"), "signed_sha256": signed_asset.sha256,
                                                 "source": source}, commit=False)
    case.summary = evidence.interpret(None, post["status"])
    case.summary["headline"] = ("Signed and immediately re-verified: " + post["status_text"]) if post["status"] in ("VALID_PROVENANCE", "VALID_BUT_UNTRUSTED_SIGNER") \
        else ("Signing produced a credential that did NOT verify: " + post["status_text"])
    db.commit()
    return case


def verify_upload(db: Session, data: bytes, filename: str | None, envelope: dict | None, sidecar: bytes | None) -> Case:
    case = Case(kind="verification", title="pending", media_type="image")
    db.add(case)
    db.flush()
    ing = ingest(db, case.id, data, filename)
    case.title = ing.asset.display_name
    case.media_type = ing.sniffed.media_type
    record(db, "upload", "ACCEPTED", case.id, {"mime": ing.sniffed.mime, "size_bytes": len(data), "sha256": ing.asset.sha256}, commit=False)
    res = run_verify(db, case, ing.asset, data, envelope, sidecar, label="independent verification")
    case.summary = evidence.interpret(None, res["status"])
    db.commit()
    return case


# ------------------------------------------------------------------ integrity lab

def demo_asset() -> bytes:
    """App-generated, licence-free demo image (no people)."""
    w, h = 960, 640
    img = Image.new("RGB", (w, h))
    px = img.load()
    for y in range(h):
        for x in range(w):
            px[x, y] = (int(12 + 30 * y / h), int(24 + 80 * x / w), int(60 + 120 * (x + y) / (w + h)))
    d = ImageDraw.Draw(img)
    for i in range(9):
        r = 40 + i * 28
        d.ellipse((w * 0.68 - r, h * 0.5 - r, w * 0.68 + r, h * 0.5 + r), outline=(80, 220, 230), width=2)
    d.rectangle((60, 60, 380, 300), outline=(170, 150, 255), width=4)
    d.line((60, 520, 900, 420), fill=(240, 240, 255), width=3)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    d.text((70, 80), "VERIFRAME demo asset", fill=(255, 255, 255))
    d.text((70, 100), stamp, fill=(200, 230, 255))
    img = img.filter(ImageFilter.SMOOTH)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=92)
    return buf.getvalue()


def _bit_diff(a_hex: str, b_hex: str) -> int:
    return bin(int(a_hex, 16) ^ int(b_hex, 16)).count("1")


def integrity_lab(db: Session, data: bytes | None, filename: str | None) -> Case:
    case = Case(kind="integrity_lab", title="pending", media_type="image")
    db.add(case)
    db.flush()
    generated = data is None
    if generated:
        data, filename = demo_asset(), "veriframe_demo_asset.jpg"
    ing = ingest(db, case.id, data, filename, allow_video=False)
    mime = ing.sniffed.mime
    if mime not in ("image/jpeg", "image/png"):
        from app.services.media.validation import MediaError
        raise MediaError("The Integrity Lab accepts JPEG or PNG images.", "UNSUPPORTED_FORMAT")
    case.title = ing.asset.display_name
    record(db, "upload", "ACCEPTED", case.id, {"mime": mime, "sha256": ing.asset.sha256, "generated_demo_asset": generated}, commit=False)

    # 1. sign (C2PA embedded) + detached envelope over the signed bytes
    signed, _ = c2pa_adapter.sign(data, mime, ing.asset.display_name, workflow="upload", software_agent="VERIFRAME Integrity Lab",
                                  description="Integrity Lab demonstration asset signed by the VERIFRAME demo service.")
    ext = _ext_for(mime)
    stem = _stem(ing.asset.display_name)
    signed_asset = add_derived_asset(db, case.id, signed, mime, ext, "signed", f"{stem}_signed{ext}")
    env = ed25519_envelope.create_envelope(signed, mime, case_id=case.id, source="integrity_lab", note="Integrity Lab")
    import json as _json
    env_asset = add_derived_asset(db, case.id, _json.dumps(env, indent=2).encode(), "application/json", ".json", "envelope",
                                  f"{stem}_signed.veriframe-sig.json")
    record(db, "sign", "SIGNED", case.id, {"signed_sha256": signed_asset.sha256, "context": "integrity_lab"}, commit=False)

    # 2. verify the clean signed copy
    v_clean = run_verify(db, case, signed_asset, signed, env, label="clean signed copy")

    # 3. byte-level tamper on a COPY (manifest stays embedded)
    t_bytes, t_desc = tamper.byte_level_tamper(signed, mime)
    t_asset = add_derived_asset(db, case.id, t_bytes, mime, ext, "tampered_bytes", f"{stem}_signed_TAMPERED_bytes{ext}")
    v_bytes = run_verify(db, case, t_asset, t_bytes, env, label="byte-level tampered copy")

    # 4. visual edit + re-encode on a COPY (manifest stripped)
    e_bytes, e_desc = tamper.visual_edit_reencode(signed)
    e_asset = add_derived_asset(db, case.id, e_bytes, "image/jpeg", ".jpg", "tampered_visual", f"{stem}_signed_EDITED_reencoded.jpg")
    v_edit = run_verify(db, case, e_asset, e_bytes, env, label="visually edited & re-encoded copy")

    def cmp(a: Asset, desc: str, v: dict) -> dict:
        d = hashing.phash_distance(signed_asset.phash, a.phash) if a.phash and signed_asset.phash else None
        return {
            "asset_id": a.id, "description": desc, "sha256": a.sha256,
            "sha256_bits_changed": _bit_diff(signed_asset.sha256, a.sha256),
            "bytes_changed": sum(1 for x, y in zip(signed, open(storage.path_for(a.stored_name), "rb").read()) if x != y) + abs(len(signed) - a.size_bytes),
            "size_bytes": a.size_bytes,
            "verification": {"status": v["status"], "c2pa_status": v["c2pa"]["status"], "detached_status": (v.get("detached") or {}).get("status"),
                             "c2pa_steps": v["c2pa"].get("steps"), "detached_steps": (v.get("detached") or {}).get("steps"),
                             "c2pa_failures": (v["c2pa"].get("validation_codes") or {}).get("failure")},
            "phash": a.phash, "phash_distance_to_signed": d,
            "phash_label": hashing.similarity_label(d) if d is not None else None,
        }

    result = {
        "generated_demo_asset": generated,
        "original": {"asset_id": ing.asset.id, "sha256": ing.asset.sha256, "phash": ing.asset.phash, "size_bytes": ing.asset.size_bytes,
                     "note": "Your original file is stored unchanged; all edits below are made on separate copies."},
        "signed": {"asset_id": signed_asset.id, "sha256": signed_asset.sha256, "phash": signed_asset.phash, "size_bytes": signed_asset.size_bytes,
                   "envelope_asset_id": env_asset.id,
                   "verification": {"status": v_clean["status"], "c2pa_status": v_clean["c2pa"]["status"],
                                    "detached_status": (v_clean.get("detached") or {}).get("status"),
                                    "c2pa_steps": v_clean["c2pa"].get("steps"), "detached_steps": (v_clean.get("detached") or {}).get("steps")}},
        "tampered_bytes": cmp(t_asset, t_desc, v_bytes),
        "tampered_visual": cmp(e_asset, e_desc, v_edit),
        "expectations_met": {
            "clean_verifies": v_clean["status"] == "VALID_PROVENANCE",
            "byte_tamper_detected": v_bytes["status"] == "TAMPERED_OR_INVALID",
            "visual_edit_detected_by_detached_signature": (v_edit.get("detached") or {}).get("status") == "TAMPERED_OR_INVALID",
            "visual_edit_strips_embedded_manifest": v_edit["c2pa"]["status"] == "NO_PROVENANCE_FOUND",
        },
    }
    ok = all(result["expectations_met"].values())
    db.add(ProvenanceRecord(case_id=case.id, asset_id=signed_asset.id, operation="tamper_test",
                            status="TAMPER_DETECTED" if ok else "UNEXPECTED_RESULT",
                            signature_valid=None, signer_trusted=None, signer=None, details=result))
    record(db, "tamper_test", "TAMPER_DETECTED" if ok else "UNEXPECTED_RESULT", case.id, result["expectations_met"], commit=False)
    case.summary = {"headline": ("Clean copy verified; both tampered copies failed integrity verification as expected."
                                 if ok else "Integrity Lab produced an unexpected result — inspect the steps."),
                    "tone": "positive" if ok else "critical", "lab": True}
    db.commit()
    return case


def file_path(asset: Asset) -> Path:
    return storage.path_for(asset.stored_name)
