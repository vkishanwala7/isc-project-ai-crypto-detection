from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import Asset, AuditEvent, Case


def asset_out(a: Asset) -> dict:
    return {
        "id": a.id, "role": a.role, "display_name": a.display_name, "mime": a.mime, "size_bytes": a.size_bytes,
        "sha256": a.sha256, "phash": a.phash, "width": a.width, "height": a.height, "duration_s": a.duration_s,
        "url": f"/api/files/{a.id}", "download_url": f"/api/files/{a.id}?download=1",
    }


def _primary_asset(c: Case) -> Asset | None:
    for role in ("original", "signed"):
        for a in c.assets:
            if a.role == role and (a.mime.startswith("image/") or a.mime.startswith("video/")):
                return a
    return None


def case_summary(c: Case) -> dict:
    ai = c.analyses[-1] if c.analyses else None
    verify_recs = [p for p in c.provenance if p.operation == "verify"]
    prov = verify_recs[0] if verify_recs else (c.provenance[-1] if c.provenance else None)
    pa = _primary_asset(c)
    return {
        "id": c.id, "created_at": c.created_at, "kind": c.kind, "title": c.title, "media_type": c.media_type,
        "is_sample": c.is_sample, "sample_label": c.sample_label,
        "ai_verdict": ai.verdict if ai and ai.status == "COMPLETED" else (ai.status if ai else None),
        "ai_score": ai.score if ai else None,
        "provenance_status": prov.status if prov else None,
        "headline": (c.summary or {}).get("headline"), "tone": (c.summary or {}).get("tone"),
        "thumbnail_url": f"/api/files/{pa.id}" if pa and pa.mime.startswith("image/") else None,
    }


def case_detail(db: Session, c: Case) -> dict:
    events = db.query(AuditEvent).filter(AuditEvent.case_id == c.id).order_by(AuditEvent.ts.asc(), AuditEvent.id.asc()).all()
    return {
        **case_summary(c),
        "sample_source": c.sample_source,
        "summary": c.summary,
        "assets": [asset_out(a) for a in c.assets],
        "analyses": [{
            "id": a.id, "created_at": a.created_at, "asset_id": a.asset_id, "status": a.status, "verdict": a.verdict,
            "reason": a.reason, "score": a.score, "threshold": a.threshold, "model_name": a.model_name,
            "model_version": a.model_version, "duration_ms": a.duration_ms, "details": a.details,
        } for a in c.analyses],
        "provenance": [{
            "id": p.id, "created_at": p.created_at, "asset_id": p.asset_id, "operation": p.operation, "status": p.status,
            "signature_valid": p.signature_valid, "signer_trusted": p.signer_trusted, "signer": p.signer, "details": p.details,
        } for p in c.provenance],
        "timeline": [{"ts": e.ts, "action": e.action, "result": e.result, "details": e.details} for e in events],
        "share_ref": f"VF-{c.id[:8].upper()}-{c.id[8:12].upper()}",
    }


def resolve_ref(db: Session, ref: str) -> Case | None:
    """Accept a full case id or a share reference like VF-1A2B3C4D-5E6F."""
    ref = ref.strip()
    if ref.upper().startswith("VF-"):
        parts = ref.upper().split("-")
        if len(parts) == 3 and len(parts[1]) == 8 and len(parts[2]) == 4:
            prefix = (parts[1] + parts[2]).lower()
            if all(ch in "0123456789abcdef" for ch in prefix):
                return db.query(Case).filter(Case.id.like(prefix + "%")).first()
        return None
    if len(ref) == 32 and all(ch in "0123456789abcdef" for ch in ref.lower()):
        return db.get(Case, ref.lower())
    return None
