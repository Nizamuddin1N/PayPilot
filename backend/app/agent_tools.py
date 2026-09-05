"""Tool implementations the buyer agent calls. Separate from the REST test-harness
endpoints in routers/orders.py because these share ONE session_id across a whole
conversation (needed for get_daily_spend), whereas the REST endpoints mint a fresh
session_id per one-shot order (no agent involved there)."""

import json
import uuid

from sqlalchemy.orm import Session

from app.audit import log_audit
from app.guardrails import check_guardrails
from app.models import Order, Product
from app.razorpay_client import create_razorpay_order


def search_catalog_impl(db: Session, session_id: str, category: str | None, max_price_inr: int | None, tags: list | None) -> dict:
    query = db.query(Product)
    if category:
        query = query.filter(Product.category == category)
    if max_price_inr is not None:
        query = query.filter(Product.price_inr <= max_price_inr)
    products = query.all()

    if tags:
        wanted = {t.strip().lower() for t in tags}
        products = [
            p for p in products
            if wanted & {t.lower() for t in (json.loads(p.tags) if p.tags else [])}
        ]

    results = [
        {
            "id": p.id, "name": p.name, "price_inr": p.price_inr,
            "category": p.category, "stock": p.stock, "tags": json.loads(p.tags) if p.tags else [],
        }
        for p in products
    ]
    log_audit(db, session_id, "catalog_query", {
        "filters": {"category": category, "max_price_inr": max_price_inr, "tags": tags},
        "result_count": len(results),
    })
    return {"products": results}


def check_guardrails_impl(db: Session, session_id: str, product_id: str, amount_inr: int) -> dict:
    return check_guardrails(db, product_id, amount_inr, session_id)


def create_order_impl(db: Session, session_id: str, product_id: str) -> dict:
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        return {"error": "product not found"}
    if product.stock <= 0:
        return {"error": "out of stock"}

    rzp_order = create_razorpay_order(product.price_inr, product.id, session_id)

    order = Order(
        id=str(uuid.uuid4()),
        session_id=session_id,
        razorpay_order_id=rzp_order["id"],
        product_id=product.id,
        amount_inr=product.price_inr,
        status="created",
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    log_audit(db, session_id, "payment_initiated", {
        "order_id": order.id, "razorpay_order_id": order.razorpay_order_id,
        "product_id": product.id, "amount_inr": product.price_inr,
    })

    return {
        "order_id": order.id,
        "razorpay_order_id": order.razorpay_order_id,
        "amount_inr": order.amount_inr,
        "status": order.status,
        "product_name": product.name,
    }
