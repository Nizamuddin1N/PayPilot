import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.audit import log_audit
from app.config import RAZORPAY_KEY_ID
from app.database import get_db
from app.failure_handling import handle_payment_failure
from app.models import Order, Product
from app.razorpay_client import create_razorpay_order, verify_payment_signature
from app.schemas import CreateOrderRequest, CreateOrderResponse, DeclineResponse, OrderOut, VerifyPaymentRequest

router = APIRouter(tags=["orders"])


def _mark_paid(db: Session, order: Order, payment_id: str | None, source: str) -> None:
    """Idempotent: the client-side verify callback and the Razorpay webhook can
    both reach here for the same order. Only the first one decrements stock and
    logs the result."""
    if order.status == "paid":
        return
    order.status = "paid"
    if payment_id:
        order.razorpay_payment_id = payment_id
    product = db.query(Product).filter(Product.id == order.product_id).first()
    if product and product.stock > 0:
        product.stock -= 1
    db.commit()
    log_audit(db, order.session_id, "payment_result", {
        "order_id": order.id, "status": "captured", "amount_inr": order.amount_inr, "source": source,
    })


def _mark_failed(db: Session, order: Order, source: str) -> dict | None:
    """Idempotent, same as _mark_paid. Returns the failure_handled result (message
    + alternative product, if any) the first time; None on a repeat call, since a
    real decline can reach here both from the client and the webhook."""
    if order.status in ("paid", "failed"):
        return None
    order.status = "failed"
    db.commit()
    log_audit(db, order.session_id, "payment_result", {
        "order_id": order.id, "status": "failed", "amount_inr": order.amount_inr, "source": source,
    })
    return handle_payment_failure(db, order)


@router.post("/api/orders", response_model=CreateOrderResponse)
def create_order(req: CreateOrderRequest, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == req.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="product not found")
    if product.stock <= 0:
        raise HTTPException(status_code=409, detail="out of stock")

    session_id = str(uuid.uuid4())
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

    return CreateOrderResponse(
        order_id=order.id,
        razorpay_order_id=order.razorpay_order_id,
        razorpay_key_id=RAZORPAY_KEY_ID,
        amount_inr=order.amount_inr,
        status=order.status,
    )


@router.post("/api/orders/{order_id}/verify", response_model=OrderOut)
def verify_order(order_id: str, req: VerifyPaymentRequest, db: Session = Depends(get_db)):
    """Confirms payment from the Razorpay Checkout success callback via signature
    verification, for immediate UI feedback. The webhook (source of truth) will
    independently confirm the same order; _mark_paid is idempotent either way."""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="order not found")
    if order.razorpay_order_id != req.razorpay_order_id:
        raise HTTPException(status_code=400, detail="order mismatch")

    if not verify_payment_signature(
        req.razorpay_order_id, req.razorpay_payment_id, req.razorpay_signature
    ):
        _mark_failed(db, order, source="client_verify")
        raise HTTPException(status_code=400, detail="signature verification failed")

    _mark_paid(db, order, req.razorpay_payment_id, source="client_verify")
    db.refresh(order)
    return OrderOut(
        order_id=order.id,
        razorpay_order_id=order.razorpay_order_id,
        razorpay_payment_id=order.razorpay_payment_id,
        product_id=order.product_id,
        amount_inr=order.amount_inr,
        status=order.status,
    )


@router.post("/api/orders/{order_id}/decline", response_model=DeclineResponse)
def decline_order(order_id: str, db: Session = Depends(get_db)):
    """Called from the frontend's Razorpay Checkout payment.failed handler — the
    real-time signal that a decline just happened, so the failure-recovery
    message (section 7) can be shown immediately instead of waiting on the
    webhook round-trip. The webhook still independently confirms the same
    order; _mark_failed's idempotency guard means only one of them logs it."""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="order not found")

    result = _mark_failed(db, order, source="client_decline")
    if result is None:
        result = {"message": "This order has already been resolved.", "alternative": None}
    return DeclineResponse(**result)


@router.get("/api/orders/{order_id}", response_model=OrderOut)
def get_order(order_id: str, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="order not found")
    return OrderOut(
        order_id=order.id,
        razorpay_order_id=order.razorpay_order_id,
        razorpay_payment_id=order.razorpay_payment_id,
        product_id=order.product_id,
        amount_inr=order.amount_inr,
        status=order.status,
    )
