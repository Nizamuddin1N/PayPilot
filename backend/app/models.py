from sqlalchemy import Column, Integer, String, Text, TIMESTAMP
from sqlalchemy.sql import func

from app.database import Base

# audit_log.event_type values (plan section 2): catalog_query, candidate_selected,
# guardrail_check, guardrail_blocked, confirmation_requested, payment_initiated,
# payment_result, failure_handled, llm_unavailable


class Product(Base):
    """Agent-readable catalog entry. price_inr is WHOLE RUPEES (see plan section 0)."""

    __tablename__ = "products"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    price_inr = Column(Integer, nullable=False)
    category = Column(String, nullable=False)
    stock = Column(Integer, nullable=False)
    policy_returns = Column(Text)
    policy_shipping = Column(Text)
    tags = Column(Text)  # JSON array, stored as string


class Order(Base):
    """Transaction lifecycle. amount_inr is WHOLE RUPEES; paise conversion happens
    only in app.razorpay_client.create_razorpay_order()."""

    __tablename__ = "orders"

    id = Column(String, primary_key=True)
    session_id = Column(String, nullable=False)
    razorpay_order_id = Column(String)
    razorpay_payment_id = Column(String)
    product_id = Column(String, nullable=False)
    amount_inr = Column(Integer, nullable=False)
    status = Column(String, nullable=False, default="created")
    created_at = Column(TIMESTAMP, server_default=func.now())


class Guardrail(Base):
    """Bounds the agent operates within. All amounts are WHOLE RUPEES (plan section 0)."""

    __tablename__ = "guardrails"

    id = Column(Integer, primary_key=True)
    max_txn_inr = Column(Integer, nullable=False)
    confirm_above_inr = Column(Integer, nullable=False)
    blocked_categories = Column(Text)  # JSON array, stored as string
    max_daily_spend_inr = Column(Integer, nullable=False)


class AuditLog(Base):
    """Every decision + action, timestamped. detail is structured JSON (as text),
    not free text; amounts inside it are rupees, matching amount_inr everywhere else."""

    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, nullable=False)
    event_type = Column(String, nullable=False)
    detail = Column(Text, nullable=False)  # JSON, stored as string
    created_at = Column(TIMESTAMP, server_default=func.now())
