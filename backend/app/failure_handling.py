"""Failure handling (plan section 7). Runs whenever a payment fails, regardless
of source (webhook or client-side decline) — checks whether the product is ALSO
out of stock right now (a real race: stock can drop between order creation and
payment completion) and gives a smarter recovery message than a bare retry
prompt when it is."""

import json

from sqlalchemy.orm import Session

from app.audit import log_audit
from app.models import Order, Product


def find_alternative(db: Session, category: str, price_inr: int, exclude_product_id: str, tolerance: float = 0.15) -> Product | None:
    low = price_inr * (1 - tolerance)
    high = price_inr * (1 + tolerance)
    return (
        db.query(Product)
        .filter(
            Product.category == category,
            Product.id != exclude_product_id,
            Product.stock > 0,
            Product.price_inr >= low,
            Product.price_inr <= high,
        )
        .order_by(Product.price_inr)
        .first()
    )


def _product_summary(p: Product) -> dict:
    return {"id": p.id, "name": p.name, "price_inr": p.price_inr, "stock": p.stock, "tags": json.loads(p.tags) if p.tags else []}


def handle_payment_failure(db: Session, order: Order) -> dict:
    product = db.query(Product).filter(Product.id == order.product_id).first()

    if product and product.stock <= 0:
        alt = find_alternative(db, product.category, product.price_inr, exclude_product_id=product.id)
        log_audit(db, order.session_id, "failure_handled", {
            "order_id": order.id,
            "cause": "out_of_stock",
            "action": "suggested_alternative" if alt else "no_alternative_available",
            "alternative_id": alt.id if alt else None,
        })
        if alt:
            message = f"That item is out of stock — here's a similar option within your budget: {alt.name} (₹{alt.price_inr})."
        else:
            message = "That item is out of stock and no close alternative was found."
        return {"message": message, "alternative": _product_summary(alt) if alt else None}

    log_audit(db, order.session_id, "failure_handled", {
        "order_id": order.id, "cause": "payment_declined", "action": "retry_prompt",
    })
    return {"message": "Payment didn't go through — want to try a different card or method?", "alternative": None}
