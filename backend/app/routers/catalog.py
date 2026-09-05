import json
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Product
from app.schemas import ProductOut, QuoteOut

router = APIRouter(tags=["catalog"])


def _to_out(p: Product) -> ProductOut:
    return ProductOut(
        id=p.id,
        name=p.name,
        description=p.description,
        price_inr=p.price_inr,
        category=p.category,
        stock=p.stock,
        policy_returns=p.policy_returns,
        policy_shipping=p.policy_shipping,
        tags=json.loads(p.tags) if p.tags else [],
    )


@router.get("/api/catalog", response_model=list[ProductOut])
def get_catalog(
    category: Optional[str] = None,
    max_price: Optional[int] = None,
    tags: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Product)
    if category:
        query = query.filter(Product.category == category)
    if max_price is not None:
        query = query.filter(Product.price_inr <= max_price)
    products = query.all()

    if tags:
        wanted = {t.strip().lower() for t in tags.split(",") if t.strip()}
        products = [
            p
            for p in products
            if wanted & {t.lower() for t in (json.loads(p.tags) if p.tags else [])}
        ]

    return [_to_out(p) for p in products]


@router.get("/api/catalog/{product_id}/quote", response_model=QuoteOut)
def get_quote(product_id: str, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="product not found")

    expires = datetime.now(timezone.utc) + timedelta(minutes=10)
    return QuoteOut(
        product_id=product.id,
        price_inr=product.price_inr,
        available=product.stock > 0,
        quote_expires_at=expires.isoformat(),
    )
