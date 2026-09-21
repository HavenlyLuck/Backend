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
    entry_number: int,
) -> RaffleEntry:
    entry = RaffleEntry(
        raffle_product_id=raffle_product_id,
        user_id=user_id,
        ticket_count=ticket_count,
        points_spent=points_spent,
        entry_number=entry_number,
    )
    db.add(entry)
    db.flush()
    return entry


def get_user_total_ticket_count(db: Session, raffle_product_id: int, user_id: int) -> int:
    return (
        db.query(func.coalesce(func.sum(RaffleEntry.ticket_count), 0))
        .filter(RaffleEntry.raffle_product_id == raffle_product_id, RaffleEntry.user_id == user_id)
        .scalar()
    )


# 이 유저가 이 상품에 이미 응모한 적이 있다면 그때 부여받은 응모 번호를 그대로 반환 (없으면 None)
def get_existing_entry_number(db: Session, raffle_product_id: int, user_id: int) -> Optional[int]:
    entry = (
        db.query(RaffleEntry)
        .filter(RaffleEntry.raffle_product_id == raffle_product_id, RaffleEntry.user_id == user_id)
        .order_by(RaffleEntry.created_at.asc())
        .first()
    )
    return entry.entry_number if entry else None


# 이 상품에 처음 응모하는 유저에게 부여할 다음 응모 번호 (1번부터 시작, 지금까지 응모한 서로 다른 유저 수 + 1)
def get_next_entry_number(db: Session, raffle_product_id: int) -> int:
    distinct_users = (
        db.query(func.count(func.distinct(RaffleEntry.user_id)))
        .filter(RaffleEntry.raffle_product_id == raffle_product_id)
        .scalar()
    )
    return distinct_users + 1


def get_user_raffle_entries(db: Session, raffle_product_id: int, user_id: int) -> list[RaffleEntry]:
    return (
        db.query(RaffleEntry)
        .filter(RaffleEntry.raffle_product_id == raffle_product_id, RaffleEntry.user_id == user_id)
        .order_by(RaffleEntry.created_at.desc())
        .all()
    )


# 추첨 가능한 상품 목록 (관리자 추첨 화면용) — 응모 종료 시각이 지났거나, 시간이 남았어도 응모권이 매진되면 대상이 된다
def get_closed_undrawn_products(db: Session) -> list[RaffleProduct]:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    products = db.query(RaffleProduct).filter(RaffleProduct.status == "open").all()
    if not products:
        return []

    sold_map = get_sold_ticket_counts(db, [p.raffle_product_id for p in products])
    eligible = [
        p for p in products
        if p.ends_at <= now or sold_map.get(p.raffle_product_id, 0) >= p.total_slots
    ]
    eligible.sort(key=lambda p: p.ends_at)
    return eligible


# 추첨 룰렛 구슬 배치용 — 응모 번호별 총 응모권 수
def get_entrants(db: Session, raffle_product_id: int) -> list[tuple[int, int]]:
    rows = (
        db.query(RaffleEntry.entry_number, func.sum(RaffleEntry.ticket_count))
        .filter(RaffleEntry.raffle_product_id == raffle_product_id)
        .group_by(RaffleEntry.entry_number)
        .order_by(RaffleEntry.entry_number.asc())
        .all()
    )
    return [(entry_number, int(total)) for entry_number, total in rows]


# 당첨 응모 번호를 가진 유저의 user_id 조회
def get_user_id_by_entry_number(db: Session, raffle_product_id: int, entry_number: int) -> Optional[int]:
    entry = (
        db.query(RaffleEntry)
        .filter(RaffleEntry.raffle_product_id == raffle_product_id, RaffleEntry.entry_number == entry_number)
        .first()
    )
    return entry.user_id if entry else None


def save_draw_result(
    db: Session,
    product: RaffleProduct,
    winner_entry_number: int,
    winner_user_id: int,
    draw_video_url: str,
) -> RaffleProduct:
    product.winner_entry_number = winner_entry_number
    product.winner_user_id = winner_user_id
    product.draw_video_url = draw_video_url
    product.drawn_at = datetime.now(timezone.utc).replace(tzinfo=None)
    product.status = "completed"
    db.commit()
    db.refresh(product)
    return product


# 마이페이지 응모 내역 — 전체 상품에 걸친 내 응모를 상품 정보와 함께 조회
def get_user_raffle_entries_all(db: Session, user_id: int) -> list[RaffleEntry]:
    rows = (
        db.query(RaffleEntry, RaffleProduct)
        .join(RaffleProduct, RaffleEntry.raffle_product_id == RaffleProduct.raffle_product_id)
        .filter(RaffleEntry.user_id == user_id)
        .order_by(RaffleEntry.created_at.desc())
        .all()
    )
    entries = []
    for entry, product in rows:
        entry.product_name = product.product_name
        entry.image_url = product.image_url
        entry.price_krw = product.price_krw
        entry.status = product.status
        entry.ends_at = product.ends_at
        entry.winner_entry_number = product.winner_entry_number
        entry.draw_video_url = product.draw_video_url
        entries.append(entry)
    return entries
