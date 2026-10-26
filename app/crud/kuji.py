import random
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from typing import Optional

from app.models.kuji import KujiSet, KujiPrize, KujiTicket
from app.models.storage import StorageItem
from app.crud import storage as storage_crud
from app.crud import inventory as inventory_crud

_rng = random.SystemRandom()


# 쿠지 한 판 등록 — 세트, 상품, 섞은 제비를 한 트랜잭션으로 만든다
# prizes: [{tier, name, quantity, cost, image_url}] (상위상 → 하위상 순서로 정렬된 상태)
def create_kuji_set(
    db: Session,
    admin_id: int,
    title: str,
    description: Optional[str],
    image_url: Optional[str],
    ticket_price: int,
    prizes: list[dict],
    last_one_name: Optional[str],
    last_one_image_url: Optional[str],
    last_one_cost: Optional[int],
    last_one_inventory_item_id: Optional[int] = None,
) -> KujiSet:
    # 재고에서 고른 상은 그 개수만큼, 라스트원상은 1개를 이 쿠지에 묶는다 (모자라면 InventoryError)
    needs = [(p["inventory_item_id"], p["quantity"]) for p in prizes if p.get("inventory_item_id") is not None]
    if last_one_name and last_one_inventory_item_id is not None:
        needs.append((last_one_inventory_item_id, 1))
    if needs:
        inventory_crud.check_available(db, needs)
    total = sum(p["quantity"] for p in prizes)
    kuji = KujiSet(
        admin_id=admin_id,
        title=title,
        description=description,
        image_url=image_url,
        ticket_price=ticket_price,
        total_tickets=total,
        remaining_tickets=total,
        last_one_name=last_one_name,
        last_one_image_url=last_one_image_url,
        last_one_cost=last_one_cost,
    )
    db.add(kuji)
    db.flush()

    prize_rows: list[KujiPrize] = []
    for i, p in enumerate(prizes):
        row = KujiPrize(
            kuji_set_id=kuji.kuji_set_id,
            tier=p["tier"],
            grade=chr(ord("A") + i),
            name=p["name"],
            image_url=p.get("image_url"),
            quantity=p["quantity"],
            remaining_quantity=p["quantity"],
            cost=p.get("cost", 0),
            sort_order=i,
        )
        db.add(row)
        prize_rows.append(row)
    db.flush()
    for p, row in zip(prizes, prize_rows):
        if p.get("inventory_item_id") is not None:
            inventory_crud.add_link(db, p["inventory_item_id"], "kuji_prize", row.kuji_prize_id)
    if last_one_name and last_one_inventory_item_id is not None:
        inventory_crud.add_link(db, last_one_inventory_item_id, "kuji_last_one", kuji.kuji_set_id)

    bag = [row.kuji_prize_id for row in prize_rows for _ in range(row.quantity)]
    _rng.shuffle(bag)
    db.add_all(
        KujiTicket(kuji_set_id=kuji.kuji_set_id, ticket_number=n, kuji_prize_id=prize_id)
        for n, prize_id in enumerate(bag, start=1)
    )

    db.commit()
    db.refresh(kuji)
    return kuji


def get_kuji_sets(db: Session, status: Optional[str] = None) -> list[KujiSet]:
    query = db.query(KujiSet)
    if status:
        query = query.filter(KujiSet.status == status)
    return query.order_by(KujiSet.created_at.desc()).all()


def get_kuji_set(db: Session, kuji_set_id: int) -> Optional[KujiSet]:
    return db.query(KujiSet).filter(KujiSet.kuji_set_id == kuji_set_id).first()


def get_kuji_set_for_update(db: Session, kuji_set_id: int) -> Optional[KujiSet]:
    return db.query(KujiSet).filter(KujiSet.kuji_set_id == kuji_set_id).with_for_update().first()


# 뽑힌 제비만 (번호, 등급)
def get_drawn_tickets(db: Session, kuji_set_id: int) -> list[tuple[int, str]]:
    return (
        db.query(KujiTicket.ticket_number, KujiPrize.grade)
        .join(KujiPrize, KujiPrize.kuji_prize_id == KujiTicket.kuji_prize_id)
        .filter(KujiTicket.kuji_set_id == kuji_set_id, KujiTicket.drawn_at.isnot(None))
        .order_by(KujiTicket.ticket_number)
        .all()
    )


class KujiDrawError(Exception):
    pass


# 고른 제비를 뽑을 수 있는지 확인 — 판매 중이 아니거나 없는 번호면 KujiDrawError, 이미 나간 번호는 돌려준다
# 반환: (세트, 고른 제비들, 이미 나간 번호)
def check_tickets(db: Session, kuji_set_id: int, ticket_numbers: list[int], for_update: bool = False):
    query = db.query(KujiSet).filter(KujiSet.kuji_set_id == kuji_set_id)
    kuji = (query.with_for_update() if for_update else query).first()
    if not kuji:
        raise LookupError("쿠지를 찾을 수 없습니다")
    if kuji.status != "open" or kuji.remaining_tickets <= 0:
        raise KujiDrawError("판매가 끝난 쿠지입니다")

    tickets = (
        db.query(KujiTicket)
        .filter(KujiTicket.kuji_set_id == kuji_set_id, KujiTicket.ticket_number.in_(ticket_numbers))
        .all()
    )
    if len(tickets) != len(ticket_numbers):
        raise KujiDrawError("없는 제비 번호가 있습니다")
    conflicts = sorted(t.ticket_number for t in tickets if t.drawn_at is not None)
    return kuji, tickets, conflicts


# 결제가 확인된 뒤 제비를 확정한다 — 세트 행을 잠가서 같은 판의 뽑기를 한 줄로 세운다. (commit은 호출한 쪽에서)
# 고른 제비 중 하나라도 이미 나갔으면 아무것도 하지 않고 그 번호들을 돌려준다(부분 뽑기 없음 → 호출한 쪽이 결제를 취소).
# 제비 확정 · 상품 남은 개수 · 보관함 적재 · 라스트원상까지 한 트랜잭션.
# 반환: (세트, 뽑은 [(제비, 상품)], 충돌 번호, 라스트원상 받았는지)
def fulfill_kuji_draw(db: Session, kuji_set_id: int, user_id: int, ticket_numbers: list[int], amount_paid: int, payment_id: str):
    kuji, tickets, conflicts = check_tickets(db, kuji_set_id, ticket_numbers, for_update=True)
    if conflicts:
        return kuji, [], conflicts, False
    if amount_paid != kuji.ticket_price * len(tickets):
        raise KujiDrawError("결제 금액이 제비 가격과 맞지 않습니다")

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    prizes = {p.kuji_prize_id: p for p in kuji.prizes}
    won: dict[int, int] = {}
    tickets.sort(key=lambda t: ticket_numbers.index(t.ticket_number))
    for t in tickets:
        t.drawn_by_user_id = user_id
        t.drawn_at = now
        prizes[t.kuji_prize_id].remaining_quantity -= 1
        won[t.kuji_prize_id] = won.get(t.kuji_prize_id, 0) + 1

    for prize_id, qty in won.items():
        storage_crud.add_kuji_win(
            db, user_id=user_id, kuji_set_id=kuji.kuji_set_id, kuji_prize_id=prize_id,
            quantity=qty, amount_spent=kuji.ticket_price * qty, payment_id=payment_id,
        )

    kuji.remaining_tickets -= len(tickets)
    kuji.board_version += 1
    # 판을 비운 사람이 라스트원상까지 받는다
    got_last_one = kuji.remaining_tickets == 0
    if got_last_one:
        kuji.status = "sold_out"
        if kuji.last_one_name:
            kuji.last_one_user_id = user_id
            storage_crud.add_kuji_win(
                db, user_id=user_id, kuji_set_id=kuji.kuji_set_id, kuji_prize_id=None, quantity=1,
                amount_spent=None, payment_id=payment_id,
            )

    db.flush()
    return kuji, [(t, prizes[t.kuji_prize_id]) for t in tickets], [], got_last_one and bool(kuji.last_one_name)


# 이미 지급한 쿠지 결제의 결과를 다시 만든다 (결제 완료 요청이 두 번 와도 같은 결과를 돌려주기 위함)
def get_paid_draw(db: Session, kuji_set_id: int, user_id: int, ticket_numbers: list[int], payment_id: str):
    kuji = get_kuji_set(db, kuji_set_id)
    tickets = (
        db.query(KujiTicket)
        .filter(
            KujiTicket.kuji_set_id == kuji_set_id,
            KujiTicket.ticket_number.in_(ticket_numbers),
            KujiTicket.drawn_by_user_id == user_id,
        )
        .all()
    )
    tickets.sort(key=lambda t: ticket_numbers.index(t.ticket_number))
    prizes = {p.kuji_prize_id: p for p in kuji.prizes}
    # 라스트원상은 같은 결제로 보관함에 들어간 상품 없는(kuji_prize_id 없는) 항목으로 알 수 있다
    got_last_one = db.query(StorageItem).filter(
        StorageItem.payment_id == payment_id, StorageItem.kuji_prize_id.is_(None),
    ).first() is not None
    return kuji, [(t, prizes[t.kuji_prize_id]) for t in tickets], got_last_one
