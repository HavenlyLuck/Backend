import secrets
from sqlalchemy import func
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.core.config import RAFFLE_TICKET_PRICE, RAFFLE_DRAW_DELAY_SECONDS
from app.models.raffle import RaffleProduct, RaffleEntry
from app.models.user import User
from app.crud import storage as storage_crud
from app.crud import point as point_crud


def create_raffle_product(
    db: Session,
    admin_id: int,
    product_name: str,
    description: Optional[str],
    price_krw: int,
    image_url: str,
    duration_days: int,
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
        ends_at=starts_at + timedelta(days=duration_days),
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


# 추첨 가능한 상품 목록 (관리자 추첨 화면용) — 응모권이 매진된 상품만 대상이 된다.
# 시간 안에 매진되지 못한 상품은 추첨하지 않고 cancel_expired_raffles에서 취소·환급된다.
def get_closed_undrawn_products(db: Session) -> list[RaffleProduct]:
    products = db.query(RaffleProduct).filter(RaffleProduct.status == "open").all()
    if not products:
        return []

    sold_map = get_sold_ticket_counts(db, [p.raffle_product_id for p in products])
    eligible = [p for p in products if sold_map.get(p.raffle_product_id, 0) >= p.total_slots]
    eligible.sort(key=lambda p: p.ends_at)
    return eligible


# 이 상품에 응모한 유저별 총 응모권 수와 사용한 포인트
def get_user_ticket_totals(db: Session, raffle_product_id: int) -> list[tuple[int, int, int]]:
    rows = (
        db.query(RaffleEntry.user_id, func.sum(RaffleEntry.ticket_count), func.sum(RaffleEntry.points_spent))
        .filter(RaffleEntry.raffle_product_id == raffle_product_id)
        .group_by(RaffleEntry.user_id)
        .all()
    )
    return [(user_id, int(tickets), int(points)) for user_id, tickets, points in rows]


# 응모 기간이 끝났는데 매진되지 못한 상품을 취소하고, 응모자에게 사용한 운포인트를 환급한다.
# 서버 주기 작업(app/main.py의 settle_loop)에서 실행된다.
# 행 잠금 후 status == "open"인 것만 처리하므로 동시에 여러 요청이 와도 한 번만 환급된다.
def cancel_expired_raffles(db: Session) -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    expired = (
        db.query(RaffleProduct)
        .filter(RaffleProduct.status == "open", RaffleProduct.ends_at <= now)
        .with_for_update()
        .all()
    )
    if not expired:
        db.rollback()
        return

    sold_map = get_sold_ticket_counts(db, [p.raffle_product_id for p in expired])
    for product in expired:
        # 매진된 상품은 시간이 지나도 추첨 대기 상태로 남는다
        if sold_map.get(product.raffle_product_id, 0) >= product.total_slots:
            continue
        product.status = "cancelled"
        for user_id, tickets, points in get_user_ticket_totals(db, product.raffle_product_id):
            point_crud.apply_point_change(
                db,
                user_id=user_id,
                point_type="woon",
                amount=points,
                reason="refund",
                reference_id=product.raffle_product_id,
                description=f"{product.product_name} 응모 취소 환급 ({tickets}장)",
            )
    db.commit()


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
    draw_video_url: Optional[str] = None,
) -> RaffleProduct:
    product.winner_entry_number = winner_entry_number
    product.winner_user_id = winner_user_id
    product.draw_video_url = draw_video_url
    product.drawn_at = datetime.now(timezone.utc).replace(tzinfo=None)
    product.status = "completed"
    # 당첨 상품은 결과 확정과 같은 트랜잭션에서 당첨자 보관함으로 들어간다
    storage_crud.add_raffle_win(db, user_id=winner_user_id, raffle_product_id=product.raffle_product_id)
    # 낙첨자에게는 구매한 응모권 수 × 응모권 가격만큼 쌀포인트를 지급한다 (당첨자는 지급 없음)
    for user_id, tickets, _ in get_user_ticket_totals(db, product.raffle_product_id):
        if user_id == winner_user_id:
            continue
        point_crud.apply_point_change(
            db,
            user_id=user_id,
            point_type="ssal",
            amount=tickets * product.ticket_price,
            reason="raffle_consolation",
            reference_id=product.raffle_product_id,
            description=f"{product.product_name} 낙첨 보상 ({tickets}장)",
        )
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
        entry.sold_out_at = product.sold_out_at
        entry.winner_entry_number = product.winner_entry_number
        entry.draw_video_url = product.draw_video_url
        entries.append(entry)
    return entries


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def get_draw_at(product: RaffleProduct) -> Optional[datetime]:
    if product.sold_out_at is None:
        return None
    return product.sold_out_at + timedelta(seconds=RAFFLE_DRAW_DELAY_SECONDS)


# 응모권 수만큼 가중치를 둔 무작위 추첨 — 응모권 1장 = 당첨 확률 1칸
def pick_weighted_entry_number(entrants: list[tuple[int, int]]) -> int:
    total = sum(tickets for _, tickets in entrants)
    r = secrets.randbelow(total)
    for entry_number, tickets in entrants:
        if r < tickets:
            return entry_number
        r -= tickets
    return entrants[-1][0]


# 매진된 지 RAFFLE_DRAW_DELAY_SECONDS가 지난 상품을 자동으로 추첨한다 (서버 주기 작업에서 실행).
# 평소에는 "추첨할 때가 된 매진 상품"을 쿼리 한 번으로 고르고 끝나며, 해당 상품이 있을 때만 그 행을 잠근다.
# 잠근 뒤 "아직 당첨자 없음"을 다시 확인하고 확정하므로 동시에 여러 번 불려도 한 번만 추첨된다.
def run_due_draws(db: Session) -> None:
    now = _utcnow()
    due_before = now - timedelta(seconds=RAFFLE_DRAW_DELAY_SECONDS)
    sold = func.coalesce(func.sum(RaffleEntry.ticket_count), 0)
    rows = (
        db.query(RaffleProduct.raffle_product_id, RaffleProduct.sold_out_at)
        .outerjoin(RaffleEntry, RaffleEntry.raffle_product_id == RaffleProduct.raffle_product_id)
        .filter(RaffleProduct.status == "open", RaffleProduct.winner_entry_number.is_(None))
        .filter((RaffleProduct.sold_out_at.is_(None)) | (RaffleProduct.sold_out_at <= due_before))
        .group_by(RaffleProduct.raffle_product_id, RaffleProduct.sold_out_at, RaffleProduct.total_slots)
        .having(sold >= RaffleProduct.total_slots)
        .all()
    )
    db.rollback()

    for pid, _ in rows:
        product = get_raffle_product_for_update(db, pid)
        if product is None or product.status != "open" or product.winner_entry_number is not None:
            db.rollback()
            continue
        # 매진 시각이 기록되기 전에 매진된 상품은 처음 발견한 지금부터 대기 시간을 센다
        if product.sold_out_at is None:
            product.sold_out_at = now
            db.commit()
            continue
        if get_draw_at(product) > now:
            db.rollback()
            continue

        entrants = get_entrants(db, pid)
        if not entrants:
            db.rollback()
            continue
        winner_entry_number = pick_weighted_entry_number(entrants)
        winner_user_id = get_user_id_by_entry_number(db, pid, winner_entry_number)
        save_draw_result(db, product, winner_entry_number=winner_entry_number, winner_user_id=winner_user_id)


# 응모 기간 만료 취소·환급 + 자동 추첨을 한 번에
def settle_raffles(db: Session) -> None:
    cancel_expired_raffles(db)
    run_due_draws(db)


def has_entered(db: Session, raffle_product_id: int, user_id: int) -> bool:
    return (
        db.query(RaffleEntry.entry_id)
        .filter(RaffleEntry.raffle_product_id == raffle_product_id, RaffleEntry.user_id == user_id)
        .first()
        is not None
    )


# 번개 추첨 화면에 세울 응모자들 — 응모 번호별 응모권 수와 그 유저의 캐릭터 착장
def get_draw_cast(db: Session, raffle_product_id: int) -> list[dict]:
    rows = (
        db.query(RaffleEntry.entry_number, RaffleEntry.user_id, func.sum(RaffleEntry.ticket_count))
        .filter(RaffleEntry.raffle_product_id == raffle_product_id)
        .group_by(RaffleEntry.entry_number, RaffleEntry.user_id)
        .order_by(RaffleEntry.entry_number.asc())
        .all()
    )
    user_ids = {user_id for _, user_id, _ in rows}
    avatars = dict(
        db.query(User.user_id, User.avatar_config).filter(User.user_id.in_(user_ids)).all()
    ) if user_ids else {}
    return [
        {"entry_number": n, "ticket_count": int(tickets), "avatar_config": avatars.get(user_id)}
        for n, user_id, tickets in rows
    ]
