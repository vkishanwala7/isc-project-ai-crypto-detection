from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.db.models import AuditEvent

logger = logging.getLogger("veriframe.audit")


def record(db: Session, action: str, result: str, case_id: str | None = None, details: dict | None = None,
           commit: bool = True) -> AuditEvent:
    """Persist an audit event. Never put media bytes, private keys or absolute paths in `details`."""
    ev = AuditEvent(action=action, result=result, case_id=case_id, details=details or {})
    db.add(ev)
    if commit:
        db.commit()
    logger.info("audit action=%s result=%s case=%s", action, result, case_id)
    return ev
