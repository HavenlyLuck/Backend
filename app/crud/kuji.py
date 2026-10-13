import random
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from typing import Optional

from app.models.kuji import KujiSet, KujiPrize, KujiTicket
from app.crud import point as point_crud
from app.crud import storage as storage_crud

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
) -> KujiSet:
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


# 쿠지 뽑기 — 세트 행을 잠가서 같은 판의 뽑기를 한 줄로 세운다.
# 고른 제비 중 하나라도 이미 나갔으면 아무것도 하지 않고 그 번호들을 돌려준다(부분 뽑기 없음).
# 포인트 차감 · 제비 확정 · 상품 남은 개수 · 보관함 적재 · 라스트원상까지 한 트랜잭션.
# 반환: (세트, 뽑은 [(제비, 상품)], 충돌 번호, 라스트원상 받았는지, 쓴 포인트)
def draw_kuji(db: Session, kuji_set_id: int, user_id: int, ticket_numbers: list[int]):
    kuji = db.query(KujiSet).filter(KujiSet.kuji_set_id == kuji_set_id).with_for_update().first()
    if not kuji:
        raise LookupError("쿠지를 찾을 수 없습니다")
    if kuji.status != "open" or kuji.remaining_tickets <= 0:
        db.rollback()
        raise KujiDrawError("판매가 끝난 쿠지입니다")

    tickets = (
        db.query(KujiTicket)
        .filter(KujiTicket.kuji_set_id == kuji_set_id, KujiTicket.ticket_number.in_(ticket_numbers))
        .all()
    )
    if len(tickets) != len(ticket_numbers):
        db.rollback()
        raise KujiDrawError("없는 제비 번호가 있습니다")
    conflicts = sorted(t.ticket_number for t in tickets if t.drawn_at is not None)
    if conflicts:
        db.rollback()
        return kuji, [], conflicts, False, 0

    points_spent = kuji.ticket_price * len(tickets)
    try:
        point_crud.apply_point_change(
            db,
            user_id=user_id,
            point_type="woon",
            amount=-points_spent,
            reason="kuji_draw",
            reference_id=kuji.kuji_set_id,
            description=f"{kuji.title} 쿠지 {len(tickets)}장",
        )
    except ValueError as e:
        db.rollback()
        raise KujiDrawError(str(e))

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
            quantity=qty, points_spent=kuji.ticket_price * qty,
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
                db, user_id=user_id, kuji_set_id=kuji.kuji_set_id, kuji_prize_id=None, quantity=1, points_spent=None,
            )

    db.commit()
    db.refresh(kuji)
    return kuji, [(t, prizes[t.kuji_prize_id]) for t in tickets], [], got_last_one and bool(kuji.last_one_name), points_spent
