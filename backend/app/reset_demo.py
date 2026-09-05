"""Reset demo state before a live run or recording: clears all orders and
audit log entries accumulated during development, and restores product stock
to the original seed values. Leaves the guardrail config untouched.

Run with: python -m app.reset_demo
"""

from app.database import SessionLocal
from app.models import AuditLog, Order, Product
from app.seed import PRODUCTS


def reset():
    db = SessionLocal()
    try:
        orders_deleted = db.query(Order).delete()
        events_deleted = db.query(AuditLog).delete()
        for p in PRODUCTS:
            db.query(Product).filter(Product.id == p["id"]).update({"stock": p["stock"]})
        db.commit()
        print(f"Cleared {orders_deleted} orders and {events_deleted} audit events.")
        print("Restored all product stock to seed values.")
    finally:
        db.close()


if __name__ == "__main__":
    reset()
