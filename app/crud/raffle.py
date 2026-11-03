import logging
import secrets
from sqlalchemy import func
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.core.config import RAFFLE_TICKET_PRICE, RAFFLE_DRAW_DELAY_SECONDS, RAFFLE_DURATION_OVERRIDE_MINUTES
from app.models.raffle import RaffleProduct, RaffleEntry
from app.models.payment import Payment
from app.models.user import User
from app.crud import storage as storage_crud
from app.crud import point as point_crud
from app.crud import inventory as inventory_crud
from app.services import portone
from app.crud import referral as referral_crud
from app.models.free_ticket import FreeTicket


def create_raffle_product(
    db: Session,
    admin_id: int,
    product_name: str,
    description: Optional[str],
    price_krw: int,
    image_url: str,
    duration_days: int,
    inventory_item_id: Optional[int] = None,
) -> RaffleProduct:
    # 재고에서 고른 품목이면 1개를 이 응모에 묶는다 (모자라면 InventoryError)
    if inventory_item_id is not None:
        inventory_crud.check_available(db, [(inventory_item_id, 1)])
    starts_at = datetime.now(timezone.utc).replace(tzinfo=None)
    duration = (
        timedelta(minutes=RAFFLE_DURATION_OVERRIDE_MINUTES)
        if RAFFLE_DURATION_OVERRIDE_MINUTES is not None
        else timedelta(days=duration_days)
    )
    product = RaffleProduct(
        admin_id=admin_id,
        product_name=product_name,
        description=description,
        price_krw=price_krw,
        ticket_price=RAFFLE_TICKET_PRICE,
        total_slots=price_krw // RAFFLE_TICKET_PRICE,
        image_url=image_url,
        starts_at=starts_at,
        ends_at=starts_at + duration,
    )
    db.add(product)
    db.flush()
    if inventory_item_id is not None:
        inventory_crud.add_link(db, inventory_item_id, "raffle", product.raffle_product_id)
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
    amount_paid: int,
    entry_number: int,
    payment_id: Optional[str] = None,
) -> RaffleEntry:
    entry = RaffleEntry(
        raffle_product_id=raffle_product_id,
        user_id=user_id,
        ticket_count=ticket_count,
        amount_paid=amount_paid,
        entry_number=entry_number,
        payment_id=payment_id,
    )
    db.add(entry)
    db.flush()
    return entry


class RaffleEntryError(Exception):
    pass


# 응모할 수 있는 상태인지 확인 (결제 전 주문 만들 때 · 결제 후 응모권 발급할 때 둘 다)
def check_can_enter(db: Session, product: Optional[RaffleProduct], ticket_count: int) -> None:
    if ticket_count <= 0:
        raise RaffleEntryError("응모권 수는 1장 이상이어야 합니다")
    if not product:
        raise RaffleEntryError("상품을 찾을 수 없습니다")
    if product.status != "open" or product.ends_at <= _utcnow():
        raise RaffleEntryError("마감된 응모입니다")
    sold = get_sold_ticket_count(db, product.raffle_product_id)
    if sold + ticket_count > product.total_slots:
        raise RaffleEntryError("남은 응모권이 부족합니다")


# 결제가 확인된 뒤 응모권을 발급한다 (commit은 호출한 쪽에서). 발급할 수 없으면 RaffleEntryError
def fulfill_raffle_entry(
    db: Session, raffle_product_id: int, user_id: int, ticket_count: int, amount_paid: int, payment_id: str,
) -> RaffleEntry:
    # 행 잠금으로 조회 → 동시 응모 시에도 total_slots를 넘겨 팔지 않도록 보장
    product = get_raffle_product_for_update(db, raffle_product_id)
    check_can_enter(db, product, ticket_count)
    if amount_paid != ticket_count * product.ticket_price:
        raise RaffleEntryError("결제 금액이 응모권 가격과 맞지 않습니다")
    sold = get_sold_ticket_count(db, raffle_product_id)

    # 이미 이 상품에 응모한 적이 있으면 그 번호를 그대로 쓰고, 처음이면 새 번호를 부여한다
    entry_number = get_existing_entry_number(db, raffle_product_id, user_id)
    if entry_number is None:
        entry_number = get_next_entry_number(db, raffle_product_id)

    entry = create_raffle_entry(
        db,
        raffle_product_id=raffle_product_id,
        user_id=user_id,
        ticket_count=ticket_count,
        amount_paid=amount_paid,
        entry_number=entry_number,
        payment_id=payment_id,
    )
    # 이번 구매로 매진됐으면 매진 시각을 남긴다 — 이 시각부터 RAFFLE_DRAW_DELAY_SECONDS 뒤에 자동 추첨
    if sold + ticket_count >= product.total_slots:
        product.sold_out_at = _utcnow()
    # 추천인을 등록한 사람의 첫 응모권 구매면 본인·추천인에게 무료 응모권을 1장씩 준다
    referral_crud.grant_first_purchase_reward(db, user_id)
    return entry


# 보관함의 무료 응모권(첫 구매 선물 · 추천 응모권)으로 결제 없이 응모한다. 응모권 count장을 이 응모에 묶는다
def enter_with_free_tickets(db: Session, raffle_product_id: int, user_id: int, count: int) -> RaffleEntry:
    product = get_raffle_product_for_update(db, raffle_product_id)
    check_can_enter(db, product, count)
    tickets = referral_crud.lock_unused_tickets(db, user_id, count)
    if len(tickets) < count:
        raise RaffleEntryError(f"보관함에 쓸 수 있는 응모권이 {len(tickets)}장뿐이에요")
    sold = get_sold_ticket_count(db, raffle_product_id)

    entry_number = get_existing_entry_number(db, raffle_product_id, user_id)
    if entry_number is None:
        entry_number = get_next_entry_number(db, raffle_product_id)
    entry = create_raffle_entry(
        db,
        raffle_product_id=raffle_product_id,
        user_id=user_id,
        ticket_count=count,
        amount_paid=0,
        entry_number=entry_number,
        payment_id=None,
    )
    now = _utcnow()
    for t in tickets:
        t.raffle_entry_id = entry.entry_id
        t.used_at = now
    if sold + count >= product.total_slots:
        product.sold_out_at = now
    db.commit()
    db.refresh(entry)
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


# 이 상품에 처음 응모하는 유저에게 부여할 다음 응모 번호 (1번부터, 지금까지 쓴 가장 큰 번호 + 1)
# 응모자가 응모를 취소하면 번호가 비므로 "응모자 수 + 1"로 매기면 남아 있는 사람과 번호가 겹친다
def get_next_entry_number(db: Session, raffle_product_id: int) -> int:
    max_number = (
        db.query(func.coalesce(func.max(RaffleEntry.entry_number), 0))
        .filter(RaffleEntry.raffle_product_id == raffle_product_id)
        .scalar()
    )
    return int(max_number) + 1


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


# 이 상품에 응모한 유저별 총 응모권 수와 결제 금액
def get_user_ticket_totals(db: Session, raffle_product_id: int) -> list[tuple[int, int, int]]:
    rows = (
        db.query(RaffleEntry.user_id, func.sum(RaffleEntry.ticket_count), func.sum(RaffleEntry.amount_paid))
        .filter(RaffleEntry.raffle_product_id == raffle_product_id)
        .group_by(RaffleEntry.user_id)
        .all()
    )
    return [(user_id, int(tickets), int(points)) for user_id, tickets, points in rows]


# 응모 기간이 끝났는데 매진되지 못한 상품을 취소하고, 응모권 결제를 카드 취소 대기로 돌린다.
# 실제 카드 취소는 crud/payment.process_cancellations가 포트원에 요청한다 (실패해도 다음 주기에 다시 시도).
# 서버 주기 작업(app/main.py의 settle_loop)에서 실행된다.
# 행 잠금 후 status == "open"인 것만 처리하므로 동시에 여러 요청이 와도 한 번만 처리된다.
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
        _cancel_raffle(db, product, "응모 기간 안에 매진되지 않아 응모가 취소되었습니다")
    db.commit()


# 응모를 취소하고 응모권 결제를 카드 취소 대기로 돌린다 (commit은 호출한 쪽에서). 반환: 환불할 payment_id들
def _cancel_raffle(db: Session, product: RaffleProduct, reason: str) -> list[str]:
    product.status = "cancelled"
    # 무료 응모권으로 응모한 것은 보관함으로 돌려준다
    entry_ids = [eid for (eid,) in db.query(RaffleEntry.entry_id).filter(RaffleEntry.raffle_product_id == product.raffle_product_id)]
    if entry_ids:
        db.query(FreeTicket).filter(FreeTicket.raffle_entry_id.in_(entry_ids)).update(
            {"raffle_entry_id": None, "used_at": None}, synchronize_session=False,
        )
    payment_ids = [
        pid for (pid,) in db.query(Payment.payment_id)
        .join(RaffleEntry, RaffleEntry.payment_id == Payment.payment_id)
        .filter(RaffleEntry.raffle_product_id == product.raffle_product_id, Payment.status == "paid")
    ]
    if payment_ids:
        db.query(Payment).filter(Payment.payment_id.in_(payment_ids)).update(
            {"status": "cancel_requested", "cancel_reason": reason},
            synchronize_session=False,
        )
    return payment_ids


class RaffleCancelError(Exception):
    pass


# 관리자 응모 취소 — 매진 전에만. 산 사람 전원 환불, 묶어 둔 재고는 자동으로 돌아간다(crud/inventory.py)
def cancel_raffle_by_admin(db: Session, raffle_product_id: int) -> tuple[RaffleProduct, list[str]]:
    product = get_raffle_product_for_update(db, raffle_product_id)
    if not product:
        raise LookupError("상품을 찾을 수 없습니다")
    if product.status != "open":
        raise RaffleCancelError("진행 중인 응모만 취소할 수 있습니다")
    if get_sold_ticket_count(db, raffle_product_id) >= product.total_slots:
        raise RaffleCancelError("매진된 응모는 취소할 수 없습니다 (곧 추첨돼요)")
    payment_ids = _cancel_raffle(db, product, "관리자가 응모를 취소했습니다")
    db.commit()
    db.refresh(product)
    return product, payment_ids


# 응모자 본인의 응모 취소 — 매진 전·마감 전에만. ticket_count장(None이면 전부)을 취소해 판매 수량을 되돌린다.
# 최근에 산 응모권부터 취소한다:
#   - 통째로 취소되는 결제는 카드 취소 대기로 돌린다 (실제 환불은 호출한 쪽에서 바로 요청, 실패하면 주기 작업이 다시 시도)
#   - 일부만 취소되는 결제 1건은 여기서 바로 포트원 부분 취소를 하고, 실패하면 아무것도 바꾸지 않는다
# 남은 응모권이 있으면 응모 번호는 그대로 유지된다.
# 무료 응모권으로 응모한 장수는 보관함으로 돌려준다.
# 반환: (취소한 응모권 수, 남은 응모권 수, 카드 취소 대기로 돌린 payment_id들, 보관함으로 돌려준 무료 응모권 수)
def cancel_my_raffle_entries(
    db: Session, raffle_product_id: int, user_id: int, ticket_count: Optional[int] = None,
) -> tuple[int, int, list[str], int]:
    # 상품 행을 잠가서 같은 시각의 응모권 구매·자동 추첨과 겹치지 않게 한다
    product = get_raffle_product_for_update(db, raffle_product_id)
    if not product:
        raise LookupError("상품을 찾을 수 없습니다")
    if product.status != "open" or product.ends_at <= _utcnow():
        raise RaffleCancelError("진행 중인 응모만 취소할 수 있어요")
    if product.sold_out_at is not None or get_sold_ticket_count(db, raffle_product_id) >= product.total_slots:
        raise RaffleCancelError("매진된 응모는 취소할 수 없어요 (곧 추첨돼요)")

    entries = (
        db.query(RaffleEntry)
        .filter(RaffleEntry.raffle_product_id == raffle_product_id, RaffleEntry.user_id == user_id)
        .order_by(RaffleEntry.created_at.desc(), RaffleEntry.entry_id.desc())
        .all()
    )
    if not entries:
        raise RaffleCancelError("취소할 응모가 없어요")
    total = sum(e.ticket_count for e in entries)
    if ticket_count is None:
        ticket_count = total
    if not 1 <= ticket_count <= total:
        raise RaffleCancelError(f"1장부터 {total}장까지 취소할 수 있어요")

    payment_ids = [e.payment_id for e in entries if e.payment_id]
    payments = {
        p.payment_id: p for p in db.query(Payment)
        .filter(Payment.payment_id.in_(payment_ids), Payment.status == "paid")
        .with_for_update()
    } if payment_ids else {}
    # 무료 응모권 응모는 묶인 응모권 수가 장수와 같아야 한다
    free_counts = dict(
        db.query(FreeTicket.raffle_entry_id, func.count(FreeTicket.free_ticket_id))
        .filter(FreeTicket.raffle_entry_id.in_([e.entry_id for e in entries]))
        .group_by(FreeTicket.raffle_entry_id)
        .all()
    )
    for e in entries:
        ok = e.payment_id in payments if e.payment_id else free_counts.get(e.entry_id, 0) == e.ticket_count
        # 예전 포인트 응모나 이미 환불 처리 중인 결제가 섞여 있으면 화면에서 취소하지 않는다
        if not ok:
            raise RaffleCancelError("이 응모는 화면에서 취소할 수 없어요. 고객센터로 문의해 주세요")

    reason = "응모자가 응모를 취소했습니다"
    full_cancel_ids: list[str] = []
    partial: Optional[tuple[Payment, int]] = None   # (결제, 환불할 금액)
    returned = 0
    remaining = ticket_count
    for e in entries:
        if remaining == 0:
            break
        take = min(e.ticket_count, remaining)
        remaining -= take
        if not e.payment_id:
            # 무료 응모권 — 취소한 장수만큼 보관함으로 돌려준다
            returned += referral_crud.return_tickets(db, e.entry_id, take)
            if take == e.ticket_count:
                db.delete(e)
            else:
                e.ticket_count -= take
            continue
        payment = payments[e.payment_id]
        if take == e.ticket_count:
            payment.status = "cancel_requested"
            payment.cancel_reason = reason
            full_cancel_ids.append(payment.payment_id)
            db.delete(e)
        else:
            refund = take * product.ticket_price
            partial = (payment, refund)
            e.ticket_count -= take
            e.amount_paid -= refund

    if partial:
        payment, refund = partial
        try:
            portone.cancel_payment_partial(payment.payment_id, refund, payment.amount, f"{reason} (일부)")
        except portone.PortOneError:
            logging.exception("raffle partial cancel failed: %s", payment.payment_id)
            db.rollback()
            raise RaffleCancelError("카드 결제 취소에 실패했어요. 잠시 후 다시 시도해 주세요")
        # 결제 금액·장수를 남은 만큼으로 줄인다 (정산은 이 금액으로 계산된다)
        payment.amount -= refund
        payment.quantity -= refund // product.ticket_price

    db.commit()
    return ticket_count, total - ticket_count, full_cancel_ids, returned


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
    # 낙첨자에게는 돈 내고 산 응모권 수 × 응모권 가격(= 결제 금액)만큼 쌀포인트를 지급한다
    # (당첨자, 무료 응모권으로 응모한 장수는 지급 없음)
    for user_id, _, paid_amount in get_user_ticket_totals(db, product.raffle_product_id):
        if user_id == winner_user_id or paid_amount <= 0:
            continue
        point_crud.apply_point_change(
            db,
            user_id=user_id,
            amount=paid_amount,
            reason="raffle_consolation",
            reference_id=product.raffle_product_id,
            description=f"{product.product_name} 낙첨 보상 ({paid_amount // product.ticket_price}장)",
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
    users = {
        user_id: (avatar_config, nickname)
        for user_id, avatar_config, nickname in db.query(User.user_id, User.avatar_config, User.nickname)
        .filter(User.user_id.in_(user_ids)).all()
    } if user_ids else {}
    return [
        {
            "entry_number": n,
            "ticket_count": int(tickets),
            "avatar_config": users.get(user_id, (None, None))[0],
            "nickname": users.get(user_id, (None, None))[1],
        }
        for n, user_id, tickets in rows
    ]
