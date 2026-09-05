from typing import List, Optional

from pydantic import BaseModel


class ProductOut(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    price_inr: int
    category: str
    stock: int
    policy_returns: Optional[str] = None
    policy_shipping: Optional[str] = None
    tags: List[str] = []

    class Config:
        from_attributes = True


class QuoteOut(BaseModel):
    product_id: str
    price_inr: int
    available: bool
    quote_expires_at: str


class CreateOrderRequest(BaseModel):
    product_id: str


class CreateOrderResponse(BaseModel):
    order_id: str
    razorpay_order_id: str
    razorpay_key_id: str
    amount_inr: int
    currency: str = "INR"
    status: str


class VerifyPaymentRequest(BaseModel):
    order_id: str
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class OrderOut(BaseModel):
    order_id: str
    razorpay_order_id: Optional[str] = None
    razorpay_payment_id: Optional[str] = None
    product_id: str
    amount_inr: int
    status: str


class ProductAlternative(BaseModel):
    id: str
    name: str
    price_inr: int
    stock: int
    tags: List[str] = []


class DeclineResponse(BaseModel):
    message: str
    alternative: Optional[ProductAlternative] = None


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str


class ChatOrder(BaseModel):
    order_id: str
    razorpay_order_id: str
    razorpay_key_id: str
    amount_inr: int
    currency: str = "INR"
    status: str
    product_name: str


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    order: Optional[ChatOrder] = None
    upsell: Optional[str] = None
