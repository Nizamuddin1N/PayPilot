"""Guardrail layer (plan section 5). All comparisons here are rupees-to-rupees --
no unit conversion happens in this function."""

import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.audit import log_audit
from app.models import Guardrail, Order, Product


def get_guardrail_config(db: Session) -> Guardrail:
    g = db.query(Guardrail).first()
    if not g:
        raise RuntimeError("guardrail config not seeded — run app.seed")
    return g


def get_daily_spend(db: Session, session_id: str) -> int:
    """Sum of paid orders for this session, today (UTC)."""
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    orders = (
        db.query(Order)
        .filter(Order.session_id == session_id, Order.status == "paid", Order.created_at >= today_start)
        .all()
    )
    return sum(o.amount_inr for o in orders)


def check_guardrails(db: Session, product_id: str, amount_inr: int, session_id: str) -> dict:
    g = get_guardrail_config(db)
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        result = {"allowed": False, "reason": f"product '{product_id}' not found"}
        log_audit(db, session_id, "guardrail_check", {**result, "amount_inr": amount_inr, "product_id": product_id})
        return result

    blocked_categories = json.loads(g.blocked_categories) if g.blocked_categories else []

    if product.category in blocked_categories:
        result = {"allowed": False, "reason": f"category '{product.category}' is blocked"}
    elif amount_inr > g.max_txn_inr:
        result = {"allowed": False, "reason": f"₹{amount_inr} exceeds hard cap ₹{g.max_txn_inr}"}
    elif amount_inr > g.confirm_above_inr:
        result = {"allowed": "needs_confirmation", "reason": f"₹{amount_inr} exceeds ₹{g.confirm_above_inr}, human confirmation required"}
    elif get_daily_spend(db, session_id) + amount_inr > g.max_daily_spend_inr:
        result = {"allowed": False, "reason": "would exceed daily spend cap"}
    else:
        result = {"allowed": True, "reason": "within all bounds"}

    log_audit(db, session_id, "guardrail_check", {**result, "amount_inr": amount_inr, "product_id": product_id})
    return result
