from sqlalchemy import func
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.core.config import RAFFLE_TICKET_PRICE, RAFFLE_DURATION_HOURS
from app.models.raffle import RaffleProduct, RaffleEntry


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


# 응모 처리 중 동시 요청으로 응모권이 초과 판매되지 않도록 행 잠금을 건 조회
def get_raffle_product_for_update(db: Session, raffle_product_id: int) -> Optional[RaffleProduct]:
    return (
        db.query(RaffleProduct)
        .filter(RaffleProduct.raffle_product_id == raffle_product_id)
        .with_for_update()
        .first()
    )


def get_sold_ticket_count(db: Session, raffle_product_id: int) -> int:
    return (
        db.query(func.coalesce(func.sum(RaffleEntry.ticket_count), 0))
        .filter(RaffleEntry.raffle_product_id == raffle_product_id)
        .scalar()
    )


# 상품 목록 화면에서 N+1 쿼리 없이 한 번에 판매량을 조회하기 위한 함수
def get_sold_ticket_counts(db: Session, raffle_product_ids: list[int]) -> dict[int, int]:
    if not raffle_product_ids:
        return {}
    rows = (
        db.query(RaffleEntry.raffle_product_id, func.sum(RaffleEntry.ticket_count))
        .filter(RaffleEntry.raffle_product_id.in_(raffle_product_ids))
        .group_by(RaffleEntry.raffle_product_id)
        .all()
    )
    return {raffle_product_id: int(total) for raffle_product_id, total in rows}


def create_raffle_entry(
    db: Session,
    raffle_product_id: int,
    user_id: int,
    ticket_count: int,
    points_spent: int,
) -> RaffleEntry:
    entry = RaffleEntry(
        raffle_product_id=raffle_product_id,
        user_id=user_id,
        ticket_count=ticket_count,
        points_spent=points_spent,
    )
    db.add(entry)
    db.flush()
    return entry


def get_user_raffle_entries(db: Session, raffle_product_id: int, user_id: int) -> list[RaffleEntry]:
    return (
        db.query(RaffleEntry)
        .filter(RaffleEntry.raffle_product_id == raffle_product_id, RaffleEntry.user_id == user_id)
        .order_by(RaffleEntry.created_at.desc())
        .all()
    )
