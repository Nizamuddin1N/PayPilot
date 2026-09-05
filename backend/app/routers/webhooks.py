import json

from fastapi import APIRouter, Header, HTTPException, Request

import razorpay
from app.config import RAZORPAY_WEBHOOK_SECRET
from app.database import SessionLocal
from app.models import Order
from app.razorpay_client import client as rzp_client
from app.routers.orders import _mark_failed, _mark_paid

router = APIRouter(tags=["webhooks"])


@router.post("/api/webhooks/razorpay")
async def razorpay_webhook(request: Request, x_razorpay_signature: str = Header(None)):
    raw_body = await request.body()
    if not x_razorpay_signature:
        raise HTTPException(status_code=400, detail="missing signature header")

    try:
        rzp_client.utility.verify_webhook_signature(
            raw_body.decode("utf-8"), x_razorpay_signature, RAZORPAY_WEBHOOK_SECRET
        )
    except razorpay.errors.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="invalid webhook signature")

    payload = json.loads(raw_body)
    event = payload.get("event")

    db = SessionLocal()
    try:
        if event == "payment.captured":
            entity = payload["payload"]["payment"]["entity"]
            order = db.query(Order).filter(Order.razorpay_order_id == entity["order_id"]).first()
            if order:
                _mark_paid(db, order, entity["id"], source="webhook")

        elif event == "payment.failed":
            entity = payload["payload"]["payment"]["entity"]
            order = db.query(Order).filter(Order.razorpay_order_id == entity["order_id"]).first()
            if order:
                _mark_failed(db, order, source="webhook")

        elif event == "order.paid":
            order_entity = payload["payload"]["order"]["entity"]
            payment_entity = payload["payload"].get("payment", {}).get("entity", {})
            order = db.query(Order).filter(Order.razorpay_order_id == order_entity["id"]).first()
            if order:
                _mark_paid(db, order, payment_entity.get("id"), source="webhook")

        # Events we didn't ask for still get a 200 so Razorpay doesn't keep retrying.
        return {"status": "ok"}
    finally:
        db.close()
