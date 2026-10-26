from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.models.payment import Payment
from app.models.raffle import RaffleProduct, RaffleEntry
from app.models.store import StoreProduct
from app.models.kuji import KujiSet, KujiPrize
from app.models.storage import StorageItem
from app.models.user import User
from app.models.inventory import Expense
from app.crud import inventory as inventory_crud

"""
재고·자금 손익의 판매 기록 — 따로 쌓지 않고 결제 · 보관함에서 모은다.
  매출 = 카드 결제 금액 (환불된 결제는 빠진다). 쌀포인트로 산 건 매출 0
  원가 = 재고 품목에 연결된 상품이면 품목 평균 원가 × 나간 수량, 아니면 쿠지 등록 때 적은 원가(없으면 0)
  날짜(한국 시간) — 쿠지 · 결제 상점은 결제한 날, 응모는 추첨한 날, 쌀포인트 상점은 구매한 날
DB의 시각은 UTC라 한국 날짜로 바꿀 때 9시간을 더한다.
"""

KST = timedelta(hours=9)


def _utc_range(start: date, end: date) -> tuple[datetime, datetime]:
    return datetime.combine(start, datetime.min.time()) - KST, datetime.combine(end + timedelta(days=1), datetime.min.time()) - KST


def _kst_date(dt: datetime) -> str:
    return (dt + KST).date().isoformat()


def get_sales(db: Session, start: date, end: date) -> list[dict]:
    lo, hi = _utc_range(start, end)
    avg = inventory_crud.get_avg_costs(db)
    links = inventory_crud.get_link_map(db)

    def linked_cost(product_type: str, product_id: int, fallback: int = 0) -> tuple[int, Optional[int]]:
        item_id = links.get((product_type, product_id))
        return (avg.get(item_id, 0), item_id) if item_id is not None else (fallback, None)

    sales: list[dict] = []

    # 카드 결제 — 쿠지 · 결제 상점
    payments = (
        db.query(Payment, User.nickname)
        .join(User, Payment.user_id == User.user_id)
        .filter(Payment.status == "paid", Payment.order_type.in_(["kuji_draw", "store_purchase"]),
                Payment.paid_at >= lo, Payment.paid_at < hi)
        .all()
    )
    items_by_payment: dict[str, list[StorageItem]] = defaultdict(list)
    if payments:
        for item in db.query(StorageItem).filter(StorageItem.payment_id.in_([p.payment_id for p, _ in payments])):
            items_by_payment[item.payment_id].append(item)
    store_ids = {p.target_id for p, _ in payments if p.order_type == "store_purchase"}
    kuji_ids = {p.target_id for p, _ in payments if p.order_type == "kuji_draw"}
    stores = {s.store_product_id: s for s in db.query(StoreProduct).filter(StoreProduct.store_product_id.in_(store_ids))} if store_ids else {}
    kujis = {k.kuji_set_id: k for k in db.query(KujiSet).filter(KujiSet.kuji_set_id.in_(kuji_ids))} if kuji_ids else {}
    prizes = {p.kuji_prize_id: p for p in db.query(KujiPrize).filter(KujiPrize.kuji_set_id.in_(kuji_ids))} if kuji_ids else {}

    for payment, nickname in payments:
        if payment.order_type == "store_purchase":
            product = stores.get(payment.target_id)
            unit, item_id = linked_cost("store", payment.target_id)
            sales.append({
                "id": payment.payment_id, "date": _kst_date(payment.paid_at), "type": "상점", "pay": "cash",
                "title": f"{product.product_name if product else '(삭제된 상품)'} ×{payment.quantity}",
                "buyer": nickname, "revenue": payment.amount, "ssal_price": 0,
                "cost": unit * payment.quantity, "item_id": item_id,
            })
        else:
            kuji = kujis.get(payment.target_id)
            cost = 0
            for item in items_by_payment[payment.payment_id]:
                if item.kuji_prize_id is not None:
                    prize = prizes.get(item.kuji_prize_id)
                    unit, _ = linked_cost("kuji_prize", item.kuji_prize_id, prize.cost if prize else 0)
                else:  # 라스트원상
                    unit, _ = linked_cost("kuji_last_one", payment.target_id, (kuji.last_one_cost or 0) if kuji else 0)
                cost += unit * item.quantity
            sales.append({
                "id": payment.payment_id, "date": _kst_date(payment.paid_at), "type": "쿠지", "pay": "cash",
                "title": f"[쿠지] {kuji.title if kuji else '(삭제된 쿠지)'} {payment.quantity}장",
                "buyer": nickname, "revenue": payment.amount, "ssal_price": 0, "cost": cost, "item_id": None,
            })

    # 응모 — 추첨이 끝나 상품이 나간 날, 그 응모의 응모권 결제 합계가 매출
    raffles = (
        db.query(RaffleProduct, User.nickname)
        .outerjoin(User, RaffleProduct.winner_user_id == User.user_id)
        .filter(RaffleProduct.status == "completed", RaffleProduct.drawn_at >= lo, RaffleProduct.drawn_at < hi)
        .all()
    )
    if raffles:
        revenue: dict[int, int] = defaultdict(int)
        for raffle_id, amount in (
            db.query(RaffleEntry.raffle_product_id, Payment.amount)
            .join(Payment, RaffleEntry.payment_id == Payment.payment_id)
            .filter(RaffleEntry.raffle_product_id.in_([r.raffle_product_id for r, _ in raffles]), Payment.status == "paid")
        ):
            revenue[raffle_id] += amount
        for raffle, nickname in raffles:
            unit, item_id = linked_cost("raffle", raffle.raffle_product_id)
            sales.append({
                "id": f"raffle-{raffle.raffle_product_id}", "date": _kst_date(raffle.drawn_at), "type": "응모", "pay": "cash",
                "title": f"[응모] {raffle.product_name}", "buyer": nickname or "-",
                "revenue": revenue.get(raffle.raffle_product_id, 0), "ssal_price": 0, "cost": unit, "item_id": item_id,
            })

    # 쌀포인트 상점 — 매출 없이 원가만 나간다
    ssal_rows = (
        db.query(StorageItem, StoreProduct, User.nickname)
        .join(StoreProduct, StorageItem.store_product_id == StoreProduct.store_product_id)
        .join(User, StorageItem.user_id == User.user_id)
        .filter(StorageItem.source == "store", StoreProduct.pay_type == "ssal",
                StorageItem.created_at >= lo, StorageItem.created_at < hi)
        .all()
    )
    for item, product, nickname in ssal_rows:
        unit, item_id = linked_cost("store", product.store_product_id)
        sales.append({
            "id": f"storage-{item.storage_item_id}", "date": _kst_date(item.created_at), "type": "상점", "pay": "ssal",
            "title": f"[쌀포인트] {product.product_name} ×{item.quantity}", "buyer": nickname,
            "revenue": 0, "ssal_price": item.amount_spent or 0, "cost": unit * item.quantity, "item_id": item_id,
        })

    sales.sort(key=lambda s: s["date"], reverse=True)
    return sales


def get_expenses(db: Session, start: date, end: date) -> list[Expense]:
    return (
        db.query(Expense)
        .filter(Expense.spent_on >= start, Expense.spent_on <= end)
        .order_by(Expense.spent_on.desc(), Expense.expense_id.desc())
        .all()
    )


def create_expense(db: Session, spent_on: date, label: str, amount: int) -> Expense:
    expense = Expense(spent_on=spent_on, label=label, amount=amount)
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return expense


def delete_expense(db: Session, expense_id: int) -> bool:
    deleted = db.query(Expense).filter(Expense.expense_id == expense_id).delete()
    db.commit()
    return deleted > 0
