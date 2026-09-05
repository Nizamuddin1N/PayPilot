"""Isolated smoke test for the 3-tool chain: search_catalog -> check_guardrails
-> create_order. Run with: python -m app.smoke_test
Confirms the exact model ID + function-calling chain works before building the
full conversational agent on top (plan section 4.3 / agent instructions rule 6)."""

import uuid

from app.database import SessionLocal
from app.gemini_agent import run_agent_turn
from app.models import AuditLog


def main():
    session_id = str(uuid.uuid4())
    db = SessionLocal()
    try:
        prompt = (
            "I want to buy wireless earbuds, something under 2000 rupees. "
            "Find a good option, check if it's within guardrails, and place the order."
        )
        print(f"session_id: {session_id}")
        print(f"user: {prompt}\n")
        result = run_agent_turn(db, session_id, prompt)
        print(f"agent: {result['reply']}\n")
        if result["order"]:
            print(f"order created: {result['order']}\n")
        if result.get("upsell"):
            print(f"upsell: {result['upsell']}\n")

        print("--- audit trail for this session ---")
        events = (
            db.query(AuditLog)
            .filter(AuditLog.session_id == session_id)
            .order_by(AuditLog.created_at)
            .all()
        )
        for e in events:
            print(f"[{e.event_type}] {e.detail}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
