import json

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AuditLog

router = APIRouter(tags=["audit"])


@router.get("/api/audit/sessions")
def list_sessions(db: Session = Depends(get_db)):
    """Distinct sessions with their event count and most recent activity, newest
    first — lets the merchant dashboard list sessions without the operator having
    to already know a session_id."""
    rows = (
        db.query(
            AuditLog.session_id,
            func.count(AuditLog.id).label("event_count"),
            func.max(AuditLog.created_at).label("last_event_at"),
        )
        .group_by(AuditLog.session_id)
        .order_by(func.max(AuditLog.created_at).desc())
        .all()
    )
    return [
        {"session_id": r.session_id, "event_count": r.event_count, "last_event_at": r.last_event_at}
        for r in rows
    ]


@router.get("/api/audit/{session_id}")
def get_audit_trail(session_id: str, db: Session = Depends(get_db)):
    events = (
        db.query(AuditLog)
        .filter(AuditLog.session_id == session_id)
        .order_by(AuditLog.created_at)
        .all()
    )
    return {
        "session_id": session_id,
        "events": [
            {
                "id": e.id,
                "event_type": e.event_type,
                "detail": json.loads(e.detail),
                "created_at": e.created_at,
            }
            for e in events
        ],
    }
