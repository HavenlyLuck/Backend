from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional

from app.models.raffle import RaffleProduct

def create_raffle_product(
    db: Session,
    admin_id: int,
    product_name: str,
    description: Optional[str],
    price_krw: int,
    ticket_price: int,
    total_slots: int,
    image_url: str,
    starts_at: datetime,
) -> RaffleProduct:
    product = RaffleProduct(
        admin_id=admin_id,
        product_name=product_name,
        description=description,
        price_krw=price_krw,
        ticket_price=ticket_price,
        total_slots=total_slots,
        image_url=image_url,
        starts_at=starts_at,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product
