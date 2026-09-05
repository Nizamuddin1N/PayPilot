"""Razorpay integration.

THE ONLY PLACE IN THE CODEBASE that converts rupees to paise is
create_razorpay_order(), immediately before the Razorpay client call.
Everywhere else — DB, tool schemas, audit log — is whole rupees (plan section 0).
"""

import razorpay

from app.config import RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET

client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))


def create_razorpay_order(amount_inr: int, product_id: str, session_id: str) -> dict:
    amount_paise = amount_inr * 100  # <-- the one conversion, per plan section 6
    return client.order.create(
        {
            "amount": amount_paise,
            "currency": "INR",
            "notes": {"product_id": product_id, "session_id": session_id},
        }
    )


def verify_payment_signature(
    razorpay_order_id: str, razorpay_payment_id: str, razorpay_signature: str
) -> bool:
    try:
        client.utility.verify_payment_signature(
            {
                "razorpay_order_id": razorpay_order_id,
                "razorpay_payment_id": razorpay_payment_id,
                "razorpay_signature": razorpay_signature,
            }
        )
        return True
    except razorpay.errors.SignatureVerificationError:
        return False
