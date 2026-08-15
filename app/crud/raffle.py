from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.core.config import RAFFLE_TICKET_PRICE, RAFFLE_DURATION_HOURS
from app.models.raffle import RaffleProduct


def create_raffle_product(
    db: Session,
    admin_id: int,
    product_name: str,
    description: Optional[str],
    price_krw: int,
    image_url: str,
) -> RaffleProduct:
    starts_at = datetime.now(timezone.utc).replace(tzinfo=None)
    product = RaffleProduct(
        admin_id=admin_id,
        product_name=product_name,
        description=description,
        price_krw=price_krw,
        ticket_price=RAFFLE_TICKET_PRICE,
        total_slots=price_krw // RAFFLE_TICKET_PRICE,
        image_url=image_url,
        starts_at=starts_at,
        ends_at=starts_at + timedelta(hours=RAFFLE_DURATION_HOURS),
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def get_raffle_products(db: Session, status: Optional[str] = None) -> list[RaffleProduct]:
    query = db.query(RaffleProduct)
    if status:
        query = query.filter(RaffleProduct.status == status)
    return query.order_by(RaffleProduct.starts_at.desc()).all()


def get_raffle_product(db: Session, raffle_product_id: int) -> Optional[RaffleProduct]:
    return db.query(RaffleProduct).filter(RaffleProduct.raffle_product_id == raffle_product_id).first()
