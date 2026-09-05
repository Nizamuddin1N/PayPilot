"""Audit logging. Every money-affecting event gets written here as it happens —
not summarized after the fact (plan section 8 / agent instructions rule 9)."""

import json

from sqlalchemy.orm import Session

from app.models import AuditLog


def log_audit(db: Session, session_id: str, event_type: str, detail: dict) -> None:
    db.add(AuditLog(session_id=session_id, event_type=event_type, detail=json.dumps(detail)))
    db.commit()
