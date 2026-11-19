"""All HTTP routes. Grouped with OpenAPI tags; see /docs."""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import media_http_error, read_upload
from app.api.serializers import asset_out, case_detail, case_summary, resolve_ref
from app.core.config import settings
from app.db.database import get_db
from app.db.models import Analysis, Asset, AuditEvent, Case, ProvenanceRecord
from app.schemas.api import (ActivityListOut, CaseDetailOut, CaseListOut, DashboardSummary, HealthResponse)
from app.services import workflows
from app.services.ai.detector import get_detector, load_metrics, load_training_log
from app.services.audit.log import record
from app.services.media import storage
from app.services.media.validation import ACCEPTED, MediaError
from app.services.provenance import c2pa_adapter, ed25519_envelope
from app.services.provenance.keys import load_keys
from app.services.provenance.service import parse_detached
from app.services.samples import list_samples, load_sample

router = APIRouter(prefix="/api")


def _load_case(db: Session, case_id: str) -> Case:
    c = resolve_ref(db, case_id)
    if c is None:
        raise HTTPException(404, detail={"code": "CASE_NOT_FOUND", "message": "No case with that identifier."})
    return c


def _media_guard(fn, db: Session, *args, **kwargs):
    try:
        return fn(db, *args, **kwargs)
    except MediaError as e:
        db.rollback()
        record(db, "error", e.code, None, {"message": str(e)[:200]})
        raise media_http_error(e)


# ------------------------------------------------------------------ system
@router.get("/health", response_model=HealthResponse, tags=["system"])
def health(db: Session = Depends(get_db)):
    info = get_detector().info()
    try:
        db.execute(func.count(Case.id).select())
        db_ok = True
    except Exception:
        db_ok = False
    try:
        km = load_keys()
        keys_ok, keys_detail = True, f"Demo signer loaded ({km.signer_summary()['subject']}); Ed25519 key {km.ed_key_id}"
    except Exception as e:  # pragma: no cover
        keys_ok, keys_detail = False, f"Key material unavailable: {type(e).__name__}"
    c2pa_ok = c2pa_adapter.available()
    subsystems = {
        "api": {"ok": True, "detail": f"{settings.app_name} API {settings.app_version}"},
        "database": {"ok": db_ok, "detail": "SQLite reachable" if db_ok else "SQLite error"},
        "ai_model": {"ok": info.available, "detail": (f"{info.name} {info.version} loaded" if info.available else info.reason)},
        "c2pa": {"ok": c2pa_ok, "detail": (f"{c2pa_adapter.sdk_info()['python_package']} / native {c2pa_adapter.sdk_info()['native_sdk']}" if c2pa_ok else "C2PA SDK unavailable")},
        "signing_keys": {"ok": keys_ok, "detail": keys_detail},
        "detached_signatures": {"ok": keys_ok, "detail": "Ed25519 educational envelope (not a C2PA credential)"},
    }
    status = "ok" if all(s["ok"] for s in subsystems.values()) else "degraded"
    return {"status": status, "version": settings.app_version, "time": datetime.now(timezone.utc), "subsystems": subsystems}


@router.get("/config", tags=["system"])
def public_config():
    return {
        "accepted_mime_types": sorted(ACCEPTED), "max_image_mb": settings.max_image_bytes // (1024 * 1024),
        "max_video_mb": settings.max_video_bytes // (1024 * 1024), "max_video_seconds": settings.max_video_seconds,
        "video_sample_frames": settings.video_sample_frames, "c2pa_sign_mime_types": sorted(c2pa_adapter.C2PA_SIGN_MIMES),
        "signer": load_keys().signer_summary(), "trust_root": load_keys().root_summary(),
        "ed25519_key_id": load_keys().ed_key_id,
    }


# ------------------------------------------------------------------ dashboard
@router.get("/dashboard/summary", response_model=DashboardSummary, tags=["dashboard"])
def dashboard_summary(include_samples: bool = False, db: Session = Depends(get_db)):
    cq = db.query(Case)
    if not include_samples:
        cq = cq.filter(Case.is_sample.is_(False))
    case_ids = [c.id for c in cq.with_entities(Case.id).all()]
    analyses = db.query(Analysis).filter(Analysis.case_id.in_(case_ids)).all() if case_ids else []
    prov = db.query(ProvenanceRecord).filter(ProvenanceRecord.case_id.in_(case_ids)).all() if case_ids else []
    verify = [p for p in prov if p.operation == "verify"]
    ai_outcomes = Counter(a.verdict if a.status == "COMPLETED" else a.status for a in analyses)
    prov_outcomes = Counter(p.status for p in verify)
    counts = {
        "assets_analyzed": len({a.case_id for a in analyses}),
        "signed_assets": sum(1 for p in prov if p.operation == "sign") + sum(1 for p in prov if p.operation == "tamper_test"),
        "verifications": len(verify),
        "valid_provenance": prov_outcomes.get("VALID_PROVENANCE", 0),
        "tampering_alerts": prov_outcomes.get("TAMPERED_OR_INVALID", 0),
        "no_provenance": prov_outcomes.get("NO_PROVENANCE_FOUND", 0),
        "integrity_lab_runs": sum(1 for p in prov if p.operation == "tamper_test"),
        "total_cases": len(case_ids),
    }
    since = datetime.now(timezone.utc) - timedelta(days=13)
    events = db.query(AuditEvent).filter(AuditEvent.ts >= since.replace(hour=0, minute=0, second=0, microsecond=0)).all()
    days = {(since + timedelta(days=i)).date().isoformat(): {"analysis": 0, "sign": 0, "verify": 0, "tamper_test": 0} for i in range(14)}
    for e in events:
        ts = e.ts if e.ts.tzinfo else e.ts.replace(tzinfo=timezone.utc)
        k = ts.date().isoformat()
        if k in days and e.action in days[k]:
            days[k][e.action] += 1
    recent = cq.order_by(Case.created_at.desc()).limit(8).all()
    return {
        "counts": counts, "ai_outcomes": dict(ai_outcomes), "provenance_outcomes": dict(prov_outcomes),
        "activity_series": [{"date": k, **v} for k, v in days.items()],
        "recent_cases": [case_summary(c) for c in recent], "sample_cases_excluded": not include_samples,
    }


# ------------------------------------------------------------------ analysis
@router.post("/analyze", response_model=CaseDetailOut, tags=["analysis"],
             summary="Upload an image/video; run AI inference and provenance inspection separately; persist a case")
async def analyze(file: UploadFile = File(...), db: Session = Depends(get_db)):
    data = await read_upload(file)
    case = _media_guard(workflows.analyze, db, data, file.filename)
    return case_detail(db, case)


# ------------------------------------------------------------------ provenance
@router.post("/provenance/sign", response_model=CaseDetailOut, tags=["provenance"],
             summary="Sign an asset (embedded C2PA where supported + detached Ed25519 envelope) and re-verify it")
async def sign(file: UploadFile = File(...), source: str = Form("upload"), note: str = Form(""), db: Session = Depends(get_db)):
    if source not in ("upload", "browser_capture"):
        raise HTTPException(422, detail={"code": "BAD_SOURCE", "message": "source must be 'upload' or 'browser_capture'"})
    data = await read_upload(file)
    case = _media_guard(workflows.sign, db, data, file.filename, source, note)
    return case_detail(db, case)


@router.post("/provenance/verify", response_model=CaseDetailOut, tags=["provenance"],
             summary="Verify media independently (embedded C2PA, optional .c2pa sidecar or VERIFRAME detached envelope)")
async def verify(file: UploadFile = File(...), credential: UploadFile | None = File(None), db: Session = Depends(get_db)):
    data = await read_upload(file)
    cred_raw = await read_upload(credential, limit=5 * 1024 * 1024) if credential is not None and credential.filename else None
    envelope, sidecar, warn = parse_detached(cred_raw, credential.filename if credential else None)
    case = _media_guard(workflows.verify_upload, db, data, file.filename, envelope, sidecar)
    if warn:
        record(db, "verify", "CREDENTIAL_WARNING", case.id, {"warning": warn})
    return case_detail(db, case)


@router.post("/provenance/verify-ref/{ref}", tags=["provenance"],
             summary="Re-verify the signed asset stored for a case/share reference created by this application")
def verify_by_ref(ref: str, db: Session = Depends(get_db)):
    c = _load_case(db, ref)
    target = next((a for a in c.assets if a.role == "signed"), None) or next((a for a in c.assets if a.role == "original"), None)
    if target is None:
        raise HTTPException(404, detail={"code": "NO_ASSET", "message": "This case has no verifiable media asset."})
    env_asset = next((a for a in c.assets if a.role == "envelope"), None)
    env = json.loads(storage.read_bytes(env_asset.stored_name)) if env_asset else None
    data = storage.read_bytes(target.stored_name)
    res = workflows.run_verify(db, c, target, data, env, label=f"re-verification by reference ({target.role} asset)")
    db.commit()
    return {"case_id": c.id, "asset": asset_out(target), "result": res}


# ------------------------------------------------------------------ integrity lab
@router.post("/integrity/tamper-demo", response_model=CaseDetailOut, tags=["integrity-lab"],
             summary="Sign an asset, verify it, tamper with separate copies and verify again (real cryptographic checks)")
async def tamper_demo(file: UploadFile | None = File(None), use_demo_asset: bool = Form(False), db: Session = Depends(get_db)):
    data = None
    filename = None
    if not use_demo_asset:
        if file is None or not file.filename:
            raise HTTPException(400, detail={"code": "NO_FILE", "message": "Upload a JPEG/PNG or set use_demo_asset=true."})
        data = await read_upload(file, limit=settings.max_image_bytes)
        filename = file.filename
    case = _media_guard(workflows.integrity_lab, db, data, filename)
    return case_detail(db, case)


# ------------------------------------------------------------------ cases
@router.get("/cases", response_model=CaseListOut, tags=["cases"])
def list_cases(kind: str | None = None, q: str | None = Query(None, max_length=80), include_samples: bool = True,
               limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), db: Session = Depends(get_db)):
    query = db.query(Case)
    if kind:
        query = query.filter(Case.kind == kind)
    if not include_samples:
        query = query.filter(Case.is_sample.is_(False))
    if q:
        like = f"%{q.strip()}%"
        query = query.filter((Case.title.ilike(like)) | (Case.id.ilike(q.strip().lower().replace("vf-", "").replace("-", "") + "%")))
    total = query.count()
    rows = query.order_by(Case.created_at.desc()).offset(offset).limit(limit).all()
    return {"items": [case_summary(c) for c in rows], "total": total}


@router.get("/cases/{case_id}", response_model=CaseDetailOut, tags=["cases"])
def get_case(case_id: str, db: Session = Depends(get_db)):
    return case_detail(db, _load_case(db, case_id))


@router.get("/cases/{case_id}/report.json", tags=["cases"])
def case_report(case_id: str, db: Session = Depends(get_db)):
    c = _load_case(db, case_id)
    detail = case_detail(db, c)
    report = {
        "report_type": "VERIFRAME evidence report", "generated_at": datetime.now(timezone.utc).isoformat(),
        "generator": f"VERIFRAME {settings.app_version}", "disclaimer": (
            "Forensic indicators only. Missing provenance does not mean media is fake; a valid signature does not prove "
            "the depicted event is true. AI scores are model estimates with documented limitations. Local academic demonstration."),
        "case": json.loads(json.dumps(detail, default=str)),
    }
    record(db, "report_export", "JSON", c.id, {})
    return JSONResponse(report, headers={"Content-Disposition": f'attachment; filename="veriframe-report-{c.id[:8]}.json"'})


@router.delete("/cases/{case_id}", tags=["cases"])
def delete_case(case_id: str, db: Session = Depends(get_db)):
    c = _load_case(db, case_id)
    names = [a.stored_name for a in c.assets]
    cid = c.id
    db.delete(c)
    db.commit()
    for n in names:
        storage.delete(n)
    record(db, "delete", "DELETED", cid, {"files_removed": len(names)})
    return {"deleted": cid}


# ------------------------------------------------------------------ files
@router.get("/files/{asset_id}", tags=["cases"], summary="Serve a stored asset by id (never by path)")
def get_file(asset_id: str, download: bool = False, db: Session = Depends(get_db)):
    if len(asset_id) != 32 or not all(ch in "0123456789abcdef" for ch in asset_id):
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Unknown asset."})
    a = db.get(Asset, asset_id)
    if a is None:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Unknown asset."})
    p: Path = storage.path_for(a.stored_name)
    if not p.exists():
        raise HTTPException(410, detail={"code": "FILE_GONE", "message": "The stored file is no longer available."})
    headers = {"X-Content-Type-Options": "nosniff", "Cache-Control": "private, max-age=300",
               "Content-Security-Policy": "default-src 'none'; img-src 'self'; media-src 'self'; style-src 'unsafe-inline'"}
    return FileResponse(p, media_type=a.mime, headers=headers,
                        filename=a.display_name if download else None,
                        content_disposition_type="attachment" if download else "inline")


# ------------------------------------------------------------------ activity
@router.get("/activity", response_model=ActivityListOut, tags=["activity"])
def activity(action: str | None = None, case_id: str | None = None, limit: int = Query(100, ge=1, le=500),
             offset: int = Query(0, ge=0), db: Session = Depends(get_db)):
    q = db.query(AuditEvent)
    if action:
        q = q.filter(AuditEvent.action == action)
    if case_id:
        q = q.filter(AuditEvent.case_id == case_id)
    total = q.count()
    rows = q.order_by(AuditEvent.ts.desc(), AuditEvent.id.desc()).offset(offset).limit(limit).all()
    return {"items": [{"id": e.id, "ts": e.ts, "action": e.action, "case_id": e.case_id, "result": e.result, "details": e.details} for e in rows],
            "total": total}


# ------------------------------------------------------------------ model
@router.get("/model/info", tags=["model"])
def model_info():
    info = get_detector().info()
    tl = load_training_log()
    return {
        "available": info.available, "reason": info.reason, "name": info.name, "version": info.version,
        "architecture": info.architecture, "threshold": info.threshold, "temperature": info.temperature,
        "checkpoint_sha256": info.checkpoint_sha256, "checkpoint_file": "model_weights/veriframe_effb0_safl.pt",
        "trained_by_this_project": info.available, "meta": info.meta,
        "preprocessing": {
            "face_detector": "MTCNN (facenet-pytorch 2.6.0, weights bundled in the PyPI wheel, MIT licence); prob >= 0.90",
            "crop": "largest faces (up to 4), square box + 30% margin, resized to 224x224 (bicubic)",
            "normalisation": "ImageNet mean/std (0.485,0.456,0.406)/(0.229,0.224,0.225)",
            "training_recompression": "all training crops re-encoded as JPEG q=92; class-agnostic quality augmentation (resolution loss, blur, noise, JPEG, colour) during training",
        },
        "decision": {"threshold": info.threshold, "inconclusive_band": "threshold ± 0.10",
                     "image_aggregation": "max over faces", "video_aggregation": "mean over face-containing sampled frames"},
        "dataset": {"name": "SAFL — Synthetic and Authentic Forensic Lab dataset (images + face frames from all 416 videos), plus webcam clips of 4 team members recorded with consent (not redistributed)",
                    "source": "https://github.com/oigres5/SAFL", "license": "CC BY 4.0 (underlying CelebA/Celeb-DF terms also apply)",
                    "commit": "bfc0cb9dc5b00ba071a83abb50ac24d3c92b87df"},
        "training": tl,
    }


@router.get("/model/metrics", tags=["model"])
def model_metrics():
    m = load_metrics()
    if not m:
        return {"available": False, "message": "No held-out evaluation has been computed (model not trained in this installation)."}
    rob = settings.model_dir / "robustness.json"
    return {"available": True, **m, "robustness": json.loads(rob.read_text()) if rob.exists() else None}


# ------------------------------------------------------------------ demo workspace
@router.get("/samples", tags=["demo"])
def samples():
    return list_samples()


@router.post("/samples/{sample_id}/analyze", response_model=CaseDetailOut, tags=["demo"])
def analyze_sample(sample_id: str, db: Session = Depends(get_db)):
    s = load_sample(sample_id)
    if s is None:
        raise HTTPException(404, detail={"code": "SAMPLE_NOT_AVAILABLE", "message": "Sample not found or not downloaded. Run scripts/fetch_demo_samples.py."})
    meta, data = s
    case = _media_guard(workflows.analyze, db, data, meta["filename"], sample={"label": meta["label"], "source": meta["source"]})
    return case_detail(db, case)


@router.get("/keys/public", tags=["provenance"], summary="Public verification material (certificates and Ed25519 public key; never private keys)")
def public_keys():
    km = load_keys()
    import base64
    return {"signer_certificate_chain_pem": km.signer_chain_pem.decode(), "trust_root_pem": km.root_cert_pem.decode(),
            "ed25519_public_key_b64": base64.b64encode(km.ed_public_raw).decode(), "ed25519_key_id": km.ed_key_id,
            "envelope_label": ed25519_envelope.LABEL}
