"""
관리자 주간 장부 — 기간(한국 날짜, 양 끝 포함)의 판매 · 물건 나감 · 회차 · 입고 · 비용 · 등록 상품을 모아 준다.
따로 쌓지 않고 결제 · 응모 · 보관함 · 쿠지 · 쌀 응모권 기록에서 계산한다. 개인정보는 넣지 않는다 (user_id만).

응모 취소 · 상점 구매 취소는 응모/보관함 행을 지우므로, 카드 결제는 남아 있는 결제(payments)를 기준으로 센다.
  sales[].status — pending(아직 확정 전) / confirmed(확정) / refunded(취소·환불)
  outflows[] — 실물이 나간 기록. 상점 반품은 quantity 음수
DB 시각은 UTC라 한국 날짜 범위를 UTC로 바꿔서 거른다.
"""
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.free_ticket import FreeTicket
from app.models.inventory import InventoryItem, InventoryReceipt
from app.models.kuji import KujiPrize, KujiSet
from app.models.payment import Payment
from app.models.point import PointTransaction
from app.models.raffle import RaffleEntry, RaffleProduct
from app.models.storage import StorageItem
from app.models.store import StoreProduct
from app.crud import finance as finance_crud
from app.crud import inventory as inventory_crud

KST = timedelta(hours=9)
REFUNDED_PAYMENT = ("cancel_requested", "cancelled", "cancel_failed")
STORE_RETURN_REASON = "보관함에서 구매 취소"   # crud/storage.cancel_store_purchase가 남기는 사유
LAST_ONE_GRADE = "라스트원"


def _utc_range(start: date, end: date) -> tuple[datetime, datetime]:
    return (
        datetime.combine(start, datetime.min.time()) - KST,
        datetime.combine(end + timedelta(days=1), datetime.min.time()) - KST,
    )


def _in(at: Optional[datetime], lo: datetime, hi: datetime) -> bool:
    return at is not None and lo <= at < hi


def _raffle_status(raffle: Optional[RaffleProduct]) -> str:
    if raffle is None or raffle.status == "cancelled":
        return "refunded"
    return "confirmed" if raffle.status == "completed" else "pending"


def get_ledger(db: Session, start: date, end: date) -> dict:
    lo, hi = _utc_range(start, end)
    links = inventory_crud.get_link_map(db)   # 예전(재고 연결) 상품의 등록 상품 — catalog_item_id가 없을 때 대신 쓴다
    sales: list[dict] = []
    outflows: list[dict] = []
    round_keys: set[tuple[str, int]] = set()   # ("raffle" | "kuji" | "store", id)

    # ── 카드 결제 ──
    payments = (
        db.query(Payment)
        .filter(Payment.paid_at.isnot(None), Payment.paid_at >= lo, Payment.paid_at < hi)
        .all()
    )
    # 상점 반품은 결제한 주와 다른 주에 일어날 수 있어 따로 찾는다 (취소된 시각 기준)
    returns = (
        db.query(Payment)
        .filter(
            Payment.order_type == "store_purchase",
            Payment.paid_at.isnot(None),
            Payment.status.in_(REFUNDED_PAYMENT),
            Payment.cancel_reason.like(f"{STORE_RETURN_REASON}%"),
            func.coalesce(Payment.cancelled_at, Payment.updated_at) >= lo,
            func.coalesce(Payment.cancelled_at, Payment.updated_at) < hi,
        )
        .all()
    )

    pay_ids = [p.payment_id for p in payments]
    entry_raffle = dict(
        db.query(RaffleEntry.payment_id, RaffleEntry.raffle_product_id).filter(RaffleEntry.payment_id.in_(pay_ids))
    ) if pay_ids else {}
    raffle_ids = {p.target_id for p in payments if p.order_type == "raffle_entry"} | set(entry_raffle.values())
    funding_store_ids = {p.target_id for p in payments if p.order_type == "store_funding"}
    raffles = {
        r.raffle_product_id: r for r in db.query(RaffleProduct).filter(
            (RaffleProduct.raffle_product_id.in_(raffle_ids)) | (RaffleProduct.funding_store_product_id.in_(funding_store_ids))
        )
    } if raffle_ids or funding_store_ids else {}

    def funding_raffle(p: Payment) -> Optional[RaffleProduct]:
        rid = entry_raffle.get(p.payment_id)
        if rid is not None:
            return raffles.get(rid)
        # 응모를 취소해서 응모 행이 지워졌으면 — 그 상점 상품의 모금 중 결제 시각 전에 열린 가장 최근 것
        cands = [r for r in raffles.values() if r.funding_store_product_id == p.target_id and r.created_at and r.created_at <= p.paid_at + timedelta(minutes=5)]
        return max(cands, key=lambda r: r.created_at) if cands else None

    store_ids = {p.target_id for p in payments + returns if p.order_type == "store_purchase"}
    kuji_ids = {p.target_id for p in payments if p.order_type == "kuji_draw"}
    stores = {s.store_product_id: s for s in db.query(StoreProduct).filter(StoreProduct.store_product_id.in_(store_ids))} if store_ids else {}
    kujis = {k.kuji_set_id: k for k in db.query(KujiSet).filter(KujiSet.kuji_set_id.in_(kuji_ids))} if kuji_ids else {}

    shipping_ids = [p.payment_id for p in payments if p.order_type == "shipping_fee"]
    shipped_payments = {
        pid for (pid,) in db.query(StorageItem.shipping_payment_id)
        .filter(StorageItem.shipping_payment_id.in_(shipping_ids), StorageItem.status == "shipped")
    } if shipping_ids else set()

    def store_catalog(s: Optional[StoreProduct], store_id: int) -> Optional[int]:
        return (s.catalog_item_id if s else None) or links.get(("store", store_id))

    for p in payments:
        refunded = p.status in REFUNDED_PAYMENT
        row = {
            "id": p.payment_id, "at": p.paid_at, "user_id": p.user_id, "pay": "cash",
            "tickets": p.quantity, "amount_krw": p.amount, "amount_ssal": 0, "title": p.order_name,
        }
        if p.order_type in ("raffle_entry", "store_funding"):
            raffle = raffles.get(p.target_id) if p.order_type == "raffle_entry" else funding_raffle(p)
            if raffle:
                round_keys.add(("raffle", raffle.raffle_product_id))
            row.update(
                kind="raffle",
                round_id=f"raffle-{raffle.raffle_product_id}" if raffle else None,
                title=raffle.product_name if raffle else p.order_name,
                status="refunded" if refunded else _raffle_status(raffle),
            )
        elif p.order_type == "kuji_draw":
            kuji = kujis.get(p.target_id)
            round_keys.add(("kuji", p.target_id))
            row.update(kind="kuji", round_id=f"kuji-{p.target_id}", title=kuji.title if kuji else p.order_name,
                       status="refunded" if refunded else "confirmed")
        elif p.order_type == "store_purchase":
            s = stores.get(p.target_id)
            round_keys.add(("store", p.target_id))
            row.update(kind="store_cash", round_id=f"store-{p.target_id}", title=s.product_name if s else p.order_name,
                       amount_ssal=p.point_used or 0, status="refunded" if refunded else "confirmed")
            # 실제로 보관함에 들어간 구매(지급 성공)만 물건이 나간다 — 지급 실패로 바로 환불된 결제는 빼고, 반품은 아래에서
            delivered = p.status == "paid" or (p.cancel_reason or "").startswith(STORE_RETURN_REASON)
            if delivered:
                outflows.append({
                    "at": p.paid_at, "round_id": f"store-{p.target_id}", "catalog_item_id": store_catalog(s, p.target_id),
                    "item_name": s.product_name if s else p.order_name, "quantity": p.quantity, "reason": "store_sale",
                })
        elif p.order_type == "shipping_fee":
            row.update(kind="shipping_fee", round_id=None, title="배송비",
                       status="refunded" if refunded else ("confirmed" if p.payment_id in shipped_payments else "pending"))
        else:
            continue
        sales.append(row)

    for p in returns:
        s = stores.get(p.target_id)
        round_keys.add(("store", p.target_id))
        outflows.append({
            "at": p.cancelled_at or p.updated_at, "round_id": f"store-{p.target_id}",
            "catalog_item_id": store_catalog(s, p.target_id),
            "item_name": s.product_name if s else p.order_name, "quantity": -p.quantity, "reason": "return",
        })

    # ── 쌀 응모권으로 한 응모 (결제 없음) ──
    free_entries = (
        db.query(RaffleEntry, RaffleProduct)
        .join(RaffleProduct, RaffleProduct.raffle_product_id == RaffleEntry.raffle_product_id)
        .filter(
            RaffleEntry.payment_id.is_(None),
            RaffleEntry.created_at >= lo, RaffleEntry.created_at < hi,
            db.query(FreeTicket.free_ticket_id).filter(FreeTicket.raffle_entry_id == RaffleEntry.entry_id).exists(),
        )
        .all()
    )
    for e, raffle in free_entries:
        round_keys.add(("raffle", raffle.raffle_product_id))
        sales.append({
            "id": f"entry-{e.entry_id}", "at": e.created_at, "kind": "raffle", "round_id": f"raffle-{raffle.raffle_product_id}",
            "title": raffle.product_name, "user_id": e.user_id, "pay": "ssal_ticket", "tickets": e.ticket_count,
            "amount_krw": 0, "amount_ssal": 0, "status": _raffle_status(raffle),
        })

    # ── 쌀포인트 상점 — 실물 상품 (보관함) ──
    ssal_items = (
        db.query(StorageItem, StoreProduct)
        .join(StoreProduct, StoreProduct.store_product_id == StorageItem.store_product_id)
        .filter(StorageItem.source == "store", StoreProduct.pay_type == "ssal",
                StorageItem.created_at >= lo, StorageItem.created_at < hi)
        .all()
    )
    for item, s in ssal_items:
        round_keys.add(("store", s.store_product_id))
        sales.append({
            "id": f"storage-{item.storage_item_id}", "at": item.created_at, "kind": "store_ssal",
            "round_id": f"store-{s.store_product_id}", "title": s.product_name, "user_id": item.user_id, "pay": "ssal",
            "tickets": item.quantity, "amount_krw": 0, "amount_ssal": item.amount_spent or 0, "status": "confirmed",
        })

    # ── 쌀포인트 상점 — 쿠폰(쌀 응모권). 한 번에 산 장수가 같은 시각 · 같은 사람으로 묶인다 ──
    coupon_rows = (
        db.query(FreeTicket)
        .filter(FreeTicket.kind == "store_purchase", FreeTicket.created_at >= lo, FreeTicket.created_at < hi)
        .order_by(FreeTicket.free_ticket_id)
        .all()
    )
    groups: dict[tuple, list[FreeTicket]] = defaultdict(list)
    for t in coupon_rows:
        groups[(t.user_id, t.created_at, t.store_product_id)].append(t)
    if groups:
        first_ids = [g[0].free_ticket_id for g in groups.values()]
        spent = {
            (tx.user_id, tx.reference_id): -tx.amount
            for tx in db.query(PointTransaction).filter(
                PointTransaction.reason == "store_purchase", PointTransaction.reference_id.in_(first_ids),
            )
        }
        coupon_store_ids = {k[2] for k in groups if k[2] is not None}
        coupon_stores = {
            s.store_product_id: s for s in db.query(StoreProduct).filter(StoreProduct.store_product_id.in_(coupon_store_ids))
        } if coupon_store_ids else {}
        for (user_id, at, store_id), tickets in groups.items():
            s = coupon_stores.get(store_id)
            if store_id is not None:
                round_keys.add(("store", store_id))
            first = tickets[0].free_ticket_id
            sales.append({
                "id": f"coupon-{first}", "at": at, "kind": "store_ssal",
                "round_id": f"store-{store_id}" if store_id is not None else None,
                "title": s.product_name if s else "쌀 응모권", "user_id": user_id, "pay": "ssal", "tickets": len(tickets),
                "amount_krw": 0, "amount_ssal": spent.get((user_id, first), (s.price * len(tickets)) if s else 0),
                "status": "confirmed",
            })

    # ── 물건 나감 — 응모 당첨 · 쿠지 · 쌀포인트 상점 (보관함에 들어간 시각). 카드 상점은 위에서 결제로 셌다 ──
    items = (
        db.query(StorageItem, RaffleProduct, StoreProduct, KujiSet, KujiPrize)
        .outerjoin(RaffleProduct, StorageItem.raffle_product_id == RaffleProduct.raffle_product_id)
        .outerjoin(StoreProduct, StorageItem.store_product_id == StoreProduct.store_product_id)
        .outerjoin(KujiSet, StorageItem.kuji_set_id == KujiSet.kuji_set_id)
        .outerjoin(KujiPrize, StorageItem.kuji_prize_id == KujiPrize.kuji_prize_id)
        .filter(StorageItem.created_at >= lo, StorageItem.created_at < hi)
        .all()
    )
    for item, raffle, store, kuji, prize in items:
        base = {"at": item.created_at, "quantity": item.quantity}
        if item.source == "raffle" and raffle:
            round_keys.add(("raffle", raffle.raffle_product_id))
            outflows.append({**base, "round_id": f"raffle-{raffle.raffle_product_id}", "reason": "raffle_win",
                             "catalog_item_id": raffle.catalog_item_id or links.get(("raffle", raffle.raffle_product_id)),
                             "item_name": raffle.product_name})
        elif item.source == "kuji" and kuji:
            round_keys.add(("kuji", kuji.kuji_set_id))
            if prize:
                outflows.append({**base, "round_id": f"kuji-{kuji.kuji_set_id}", "reason": "kuji_prize",
                                 "catalog_item_id": prize.catalog_item_id or links.get(("kuji_prize", prize.kuji_prize_id)),
                                 "item_name": f"{prize.grade}상 {prize.name}"})
            else:
                outflows.append({**base, "round_id": f"kuji-{kuji.kuji_set_id}", "reason": "kuji_last_one",
                                 "catalog_item_id": kuji.last_one_catalog_item_id or links.get(("kuji_last_one", kuji.kuji_set_id)),
                                 "item_name": f"{LAST_ONE_GRADE}상 {kuji.last_one_name or ''}".strip()})
        elif item.source == "store" and store and store.pay_type == "ssal":
            outflows.append({**base, "round_id": f"store-{store.store_product_id}", "reason": "ssal_shop",
                             "catalog_item_id": store_catalog(store, store.store_product_id), "item_name": store.product_name})
    # 보관 기한이 지나 쌀포인트로 바뀐 상품 — 당첨·뽑기 때 나간 물건이 회사에 남으니 음수 (바뀐 시각 기준)
    converted = (
        db.query(StorageItem, RaffleProduct, KujiSet, KujiPrize)
        .outerjoin(RaffleProduct, StorageItem.raffle_product_id == RaffleProduct.raffle_product_id)
        .outerjoin(KujiSet, StorageItem.kuji_set_id == KujiSet.kuji_set_id)
        .outerjoin(KujiPrize, StorageItem.kuji_prize_id == KujiPrize.kuji_prize_id)
        .filter(StorageItem.status == "converted", StorageItem.converted_at >= lo, StorageItem.converted_at < hi)
        .all()
    )
    for item, raffle, kuji, prize in converted:
        if item.source == "raffle" and raffle:
            round_id = f"raffle-{raffle.raffle_product_id}"
            catalog = raffle.catalog_item_id or links.get(("raffle", raffle.raffle_product_id))
            name = raffle.product_name
        elif item.source == "kuji" and kuji:
            round_id = f"kuji-{kuji.kuji_set_id}"
            if prize:
                catalog = prize.catalog_item_id or links.get(("kuji_prize", prize.kuji_prize_id))
                name = f"{prize.grade}상 {prize.name}"
            else:
                catalog = kuji.last_one_catalog_item_id or links.get(("kuji_last_one", kuji.kuji_set_id))
                name = f"{LAST_ONE_GRADE}상 {kuji.last_one_name or ''}".strip()
        else:
            continue
        round_keys.add((round_id.split("-")[0], int(round_id.split("-")[1])))
        outflows.append({"at": item.converted_at, "round_id": round_id, "catalog_item_id": catalog,
                         "item_name": name, "quantity": -item.quantity, "reason": "storage_convert"})

    # 기간 안에 새로 연 회차도 넣는다
    for (rid,) in db.query(RaffleProduct.raffle_product_id).filter(RaffleProduct.created_at >= lo, RaffleProduct.created_at < hi):
        round_keys.add(("raffle", rid))
    for (kid,) in db.query(KujiSet.kuji_set_id).filter(KujiSet.created_at >= lo, KujiSet.created_at < hi):
        round_keys.add(("kuji", kid))
    for (sid,) in db.query(StoreProduct.store_product_id).filter(StoreProduct.created_at >= lo, StoreProduct.created_at < hi):
        round_keys.add(("store", sid))

    sales.sort(key=lambda r: (r["at"], r["id"]))
    outflows.sort(key=lambda r: r["at"])
    return {
        "sales": sales,
        "outflows": outflows,
        "rounds": _rounds(db, round_keys, links),
        "purchases": [
            {
                "receipt_id": r.receipt_id, "item_id": r.item_id, "received_at": r.received_at, "supplier": r.supplier,
                "quantity": r.quantity, "unit_cost": r.unit_cost, "memo": r.memo, "tax_free": bool(r.tax_free),
            }
            for r in db.query(InventoryReceipt)
            .filter(InventoryReceipt.received_at >= start, InventoryReceipt.received_at <= end)
            .order_by(InventoryReceipt.received_at, InventoryReceipt.receipt_id)
        ],
        "expenses": finance_crud.get_expenses(db, start, end),
        "catalog": [
            {"item_id": i.item_id, "name": i.name}
            for i in db.query(InventoryItem).order_by(InventoryItem.item_id)
        ],
    }


def _rounds(db: Session, keys: set[tuple[str, int]], links: dict) -> list[dict]:
    ids: dict[str, set[int]] = defaultdict(set)
    for kind, rid in keys:
        ids[kind].add(rid)
    rounds: list[dict] = []

    if ids["raffle"]:
        raffle_ids = list(ids["raffle"])
        sold = dict(
            db.query(RaffleEntry.raffle_product_id, func.sum(RaffleEntry.ticket_count))
            .filter(RaffleEntry.raffle_product_id.in_(raffle_ids))
            .group_by(RaffleEntry.raffle_product_id)
        )
        ssal = dict(
            db.query(RaffleEntry.raffle_product_id, func.count(FreeTicket.free_ticket_id))
            .join(FreeTicket, FreeTicket.raffle_entry_id == RaffleEntry.entry_id)
            .filter(RaffleEntry.raffle_product_id.in_(raffle_ids))
            .group_by(RaffleEntry.raffle_product_id)
        )
        for r in db.query(RaffleProduct).filter(RaffleProduct.raffle_product_id.in_(raffle_ids)):
            rounds.append({
                "round_id": f"raffle-{r.raffle_product_id}", "kind": "raffle", "title": r.product_name, "status": r.status,
                "price": r.ticket_price, "tickets_total": r.total_slots,
                "tickets_sold": int(sold.get(r.raffle_product_id) or 0), "tickets_ssal": int(ssal.get(r.raffle_product_id) or 0),
                "created_at": r.created_at,
                "closed_at": r.drawn_at if r.status == "completed" else (r.updated_at if r.status == "cancelled" else None),
                "items": [{
                    "grade": None, "catalog_item_id": r.catalog_item_id or links.get(("raffle", r.raffle_product_id)),
                    "name": r.product_name, "quantity": 1,
                }],
            })

    if ids["kuji"]:
        for k in db.query(KujiSet).filter(KujiSet.kuji_set_id.in_(ids["kuji"])):
            items = [
                {"grade": p.grade, "catalog_item_id": p.catalog_item_id or links.get(("kuji_prize", p.kuji_prize_id)),
                 "name": p.name, "quantity": p.quantity}
                for p in k.prizes if not p.point_amount   # 쌀포인트 상은 실물이 아니라 뺀다
            ]
            if k.last_one_name:
                items.append({"grade": LAST_ONE_GRADE,
                              "catalog_item_id": k.last_one_catalog_item_id or links.get(("kuji_last_one", k.kuji_set_id)),
                              "name": k.last_one_name, "quantity": 1})
            rounds.append({
                "round_id": f"kuji-{k.kuji_set_id}", "kind": "kuji", "title": k.title, "status": k.status,
                "price": k.ticket_price, "tickets_total": k.total_tickets,
                "tickets_sold": k.total_tickets - k.remaining_tickets, "tickets_ssal": 0,
                "created_at": k.created_at,
                "closed_at": k.sold_out_at or (k.updated_at if k.status == "closed" else None),
                "items": items,
            })

    if ids["store"]:
        store_ids = list(ids["store"])
        sold = dict(
            db.query(StorageItem.store_product_id, func.sum(StorageItem.quantity))
            .filter(StorageItem.store_product_id.in_(store_ids))
            .group_by(StorageItem.store_product_id)
        )
        coupons = dict(
            db.query(FreeTicket.store_product_id, func.count(FreeTicket.free_ticket_id))
            .filter(FreeTicket.store_product_id.in_(store_ids))
            .group_by(FreeTicket.store_product_id)
        )
        for s in db.query(StoreProduct).filter(StoreProduct.store_product_id.in_(store_ids)):
            sold_n = int(sold.get(s.store_product_id) or 0) + int(coupons.get(s.store_product_id) or 0)
            regular = s.sale_mode == "regular"
            status = "deleted" if s.deleted_at else ("on_sale" if regular or s.stock > 0 else "sold_out")
            rounds.append({
                "round_id": f"store-{s.store_product_id}", "kind": "store_cash" if s.pay_type == "cash" else "store_ssal",
                "title": s.product_name, "status": status, "price": s.price,
                "tickets_total": None if regular else s.stock + sold_n, "tickets_sold": sold_n, "tickets_ssal": 0,
                "created_at": s.created_at, "closed_at": s.deleted_at,
                "items": [{
                    "grade": None, "catalog_item_id": s.catalog_item_id or links.get(("store", s.store_product_id)),
                    "name": s.product_name, "quantity": None,
                }],
            })

    rounds.sort(key=lambda r: (r["created_at"] or datetime.min, r["round_id"]))
    return rounds
