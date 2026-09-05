"""Seed 18 products across 4 categories so the buyer agent has real choices
to reason over later. Run with: python -m app.seed
All prices are whole rupees (plan section 0)."""

import json

from app.database import Base, SessionLocal, engine
from app.models import Guardrail, Product

PRODUCTS = [
    # Electronics
    dict(id="ele-001", name="Wireless Earbuds", description="Bluetooth 5.3 earbuds, 24h battery with case", price_inr=1799, category="Electronics", stock=25, policy_returns="7-day return", policy_shipping="2-day shipping", tags=["audio", "wireless", "gadget"]),
    dict(id="ele-002", name="USB-C Fast Charger 65W", description="GaN charger, 65W USB-C PD", price_inr=1299, category="Electronics", stock=40, policy_returns="7-day return", policy_shipping="2-day shipping", tags=["charger", "accessory"]),
    dict(id="ele-003", name="Mechanical Keyboard", description="Hot-swappable 65% mechanical keyboard", price_inr=3499, category="Electronics", stock=15, policy_returns="10-day return", policy_shipping="3-day shipping", tags=["keyboard", "gadget", "office"]),
    dict(id="ele-004", name="Portable Power Bank 10000mAh", description="Slim power bank with dual USB-C ports", price_inr=999, category="Electronics", stock=50, policy_returns="7-day return", policy_shipping="2-day shipping", tags=["accessory", "travel"]),
    dict(id="ele-005", name="Smart Fitness Band", description="Heart-rate + SpO2 tracking, 7-day battery", price_inr=2199, category="Electronics", stock=20, policy_returns="7-day return", policy_shipping="2-day shipping", tags=["wearable", "fitness", "gadget"]),
    dict(id="ele-006", name="Bluetooth Speaker", description="Compact waterproof speaker, 12h playtime", price_inr=1599, category="Electronics", stock=0, policy_returns="7-day return", policy_shipping="2-day shipping", tags=["audio", "wireless"]),
    # Apparel
    dict(id="app-001", name="Cotton Crew T-Shirt", description="100% cotton, regular fit", price_inr=499, category="Apparel", stock=100, policy_returns="15-day return", policy_shipping="3-day shipping", tags=["clothing", "casual"]),
    dict(id="app-002", name="Running Shoes", description="Lightweight mesh running shoes", price_inr=2499, category="Apparel", stock=30, policy_returns="15-day return", policy_shipping="3-day shipping", tags=["footwear", "fitness"]),
    dict(id="app-003", name="Denim Jacket", description="Classic fit denim jacket", price_inr=2199, category="Apparel", stock=18, policy_returns="15-day return", policy_shipping="3-day shipping", tags=["clothing", "casual", "winter"]),
    dict(id="app-004", name="Wool Blend Sweater", description="Warm crew-neck sweater", price_inr=1799, category="Apparel", stock=22, policy_returns="15-day return", policy_shipping="3-day shipping", tags=["clothing", "winter"]),
    dict(id="app-005", name="Formal Leather Belt", description="Genuine leather, reversible buckle", price_inr=899, category="Apparel", stock=35, policy_returns="15-day return", policy_shipping="3-day shipping", tags=["accessory", "formal"]),
    # Home & Kitchen
    dict(id="hom-001", name="Stainless Steel Water Bottle", description="1L insulated bottle, keeps cold 24h", price_inr=699, category="Home & Kitchen", stock=60, policy_returns="10-day return", policy_shipping="3-day shipping", tags=["kitchen", "travel"]),
    dict(id="hom-002", name="Non-Stick Cookware Set", description="5-piece non-stick pan and pot set", price_inr=2999, category="Home & Kitchen", stock=12, policy_returns="10-day return", policy_shipping="4-day shipping", tags=["kitchen", "cooking"]),
    dict(id="hom-003", name="LED Desk Lamp", description="Dimmable LED lamp with USB charging port", price_inr=1099, category="Home & Kitchen", stock=28, policy_returns="10-day return", policy_shipping="3-day shipping", tags=["office", "lighting"]),
    dict(id="hom-004", name="Memory Foam Pillow", description="Cervical support memory foam pillow", price_inr=1499, category="Home & Kitchen", stock=0, policy_returns="10-day return", policy_shipping="3-day shipping", tags=["bedding", "comfort"]),
    dict(id="hom-005", name="Electric Kettle 1.5L", description="Auto shut-off, 1500W", price_inr=1399, category="Home & Kitchen", stock=24, policy_returns="10-day return", policy_shipping="3-day shipping", tags=["kitchen", "appliance"]),
    # Books & Stationery
    dict(id="bok-001", name="Hardcover Ruled Notebook", description="A5, 200 pages, dotted grid", price_inr=349, category="Books & Stationery", stock=80, policy_returns="7-day return", policy_shipping="2-day shipping", tags=["stationery", "office"]),
    dict(id="bok-002", name="Fountain Pen Set", description="2 fountain pens with ink cartridges", price_inr=799, category="Books & Stationery", stock=45, policy_returns="7-day return", policy_shipping="2-day shipping", tags=["stationery", "gift"]),
]


# Demo guardrail config, using the exact example numbers from plan section 5
# ("seed with a visible cap, e.g. ₹2000 hard cap, ₹1000 confirmation threshold").
# Blocked category and max daily spend are my own judgment call for a demo-able
# rule-based block — change freely, they're just config.
GUARDRAIL_CONFIG = dict(
    max_txn_inr=2000,
    confirm_above_inr=1000,
    blocked_categories=json.dumps(["Books & Stationery"]),
    max_daily_spend_inr=5000,
)


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        existing = db.query(Product).count()
        if existing > 0:
            print(f"Skipping product seed — {existing} products already in DB. Delete agentic_commerce.db to reseed.")
        else:
            for p in PRODUCTS:
                row = dict(p)
                row["tags"] = json.dumps(row["tags"])
                db.add(Product(**row))
            db.commit()
            print(f"Seeded {len(PRODUCTS)} products.")

        if db.query(Guardrail).count() > 0:
            print("Skipping guardrail seed — config already exists.")
        else:
            db.add(Guardrail(**GUARDRAIL_CONFIG))
            db.commit()
            print(f"Seeded guardrail config: {GUARDRAIL_CONFIG}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
