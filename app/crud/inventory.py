from collections import defaultdict
from datetime import date
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.inventory import InventoryItem, InventoryReceipt, InventoryLink
from app.models.raffle import RaffleProduct
from app.models.store import StoreProduct
from app.models.kuji import KujiSet, KujiPrize
from app.models.storage import StorageItem

"""
재고 수량은 세 칸으로 나뉜다 (등록하면 묶이고, 팔리면 빠진다):
  available(재고) — 아직 아무 상품에도 안 올린 것 = 입고 합계 − 판매 중 − 판매 완료
  reserved(판매 중) — 상품에 걸려 있는 것
  sold(판매 완료) — 팔려서 나간 것
판매 중 · 판매 완료는 저장하지 않고 연결된 상품의 지금 상태에서 계산한다.
그래서 응모 취소 · 쿠지 판매 종료 · 상점 수량 조정을 하면 남은 물건이 자동으로 재고로 돌아간다.
"""


class InventoryError(Exception):
    pass


def _link_usage(db: Session, links: list[InventoryLink]) -> dict[int, dict]:
    """link_id → {reserved, sold, product_type(raffle|kuji|store), product_id, product_name}"""
    by_type: dict[str, list[InventoryLink]] = defaultdict(list)
    for link in links:
        by_type[link.product_type].append(link)
    out: dict[int, dict] = {}

    if by_type["raffle"]:
        ids = [l.product_id for l in by_type["raffle"]]
        raffles = {r.raffle_product_id: r for r in db.query(RaffleProduct).filter(RaffleProduct.raffle_product_id.in_(ids))}
        for l in by_type["raffle"]:
            r = raffles.get(l.product_id)
            status = r.status if r else "cancelled"
            out[l.link_id] = {
                "reserved": 1 if status == "open" else 0,
                "sold": 1 if status == "completed" else 0,
                "product_type": "raffle", "product_id": l.product_id,
                "product_name": f"[응모] {r.product_name}" if r else "(삭제된 응모)",
            }

    if by_type["store"]:
        ids = [l.product_id for l in by_type["store"]]
        products = {p.store_product_id: p for p in db.query(StoreProduct).filter(StoreProduct.store_product_id.in_(ids))}
        # 보관함에 들어간 수량 = 팔린 수량 (구매 취소하면 보관함에서 빠지고 재고는 상품 stock으로 돌아간다)
        sold = dict(
            db.query(StorageItem.store_product_id, func.sum(StorageItem.quantity))
            .filter(StorageItem.store_product_id.in_(ids))
            .group_by(StorageItem.store_product_id)
        )
        for l in by_type["store"]:
            p = products.get(l.product_id)
            label = "[상점]" if p and p.pay_type == "cash" else "[쌀포인트 상점]"
            out[l.link_id] = {
                "reserved": p.stock if p else 0,
                "sold": int(sold.get(l.product_id) or 0),
                "product_type": "store", "product_id": l.product_id,
                "product_name": f"{label} {p.product_name}" if p else "(삭제된 상품)",
            }

    if by_type["kuji_prize"]:
        ids = [l.product_id for l in by_type["kuji_prize"]]
        rows = {
            prize.kuji_prize_id: (prize, kuji)
            for prize, kuji in db.query(KujiPrize, KujiSet)
            .join(KujiSet, KujiPrize.kuji_set_id == KujiSet.kuji_set_id)
            .filter(KujiPrize.kuji_prize_id.in_(ids))
        }
        for l in by_type["kuji_prize"]:
            prize, kuji = rows.get(l.product_id, (None, None))
            if not prize:
                out[l.link_id] = {"reserved": 0, "sold": 0, "product_type": "kuji", "product_id": 0, "product_name": "(삭제된 쿠지)"}
                continue
            out[l.link_id] = {
                # 판매 종료된 쿠지의 안 뽑힌 상품은 재고로 돌아간다
                "reserved": prize.remaining_quantity if kuji.status != "closed" else 0,
                "sold": prize.quantity - prize.remaining_quantity,
                "product_type": "kuji", "product_id": kuji.kuji_set_id,
                "product_name": f"[쿠지] {kuji.title} {prize.grade}상",
            }

    if by_type["kuji_last_one"]:
        ids = [l.product_id for l in by_type["kuji_last_one"]]
        kujis = {k.kuji_set_id: k for k in db.query(KujiSet).filter(KujiSet.kuji_set_id.in_(ids))}
        for l in by_type["kuji_last_one"]:
            k = kujis.get(l.product_id)
            won = bool(k and k.last_one_user_id)
            out[l.link_id] = {
                "reserved": 1 if k and not won and k.status != "closed" else 0,
                "sold": 1 if won else 0,
                "product_type": "kuji", "product_id": l.product_id,
                "product_name": f"[쿠지] {k.title} 라스트원상" if k else "(삭제된 쿠지)",
            }
    return out


def average_cost(receipts: list[InventoryReceipt]) -> int:
    qty = sum(r.quantity for r in receipts)
    return round(sum(r.quantity * r.unit_cost for r in receipts) / qty) if qty > 0 else 0


def _summaries(db: Session, items: list[InventoryItem], with_detail: bool = False) -> list[dict]:
    ids = [i.item_id for i in items]
    if not ids:
        return []
    receipts: dict[int, list[InventoryReceipt]] = defaultdict(list)
    for r in db.query(InventoryReceipt).filter(InventoryReceipt.item_id.in_(ids)):
        receipts[r.item_id].append(r)
    links: dict[int, list[InventoryLink]] = defaultdict(list)
    all_links = db.query(InventoryLink).filter(InventoryLink.item_id.in_(ids)).all()
    for l in all_links:
        links[l.item_id].append(l)
    usage = _link_usage(db, all_links)

    result = []
    for item in items:
        rs = receipts[item.item_id]
        used = [usage[l.link_id] for l in links[item.item_id]]
        total = sum(r.quantity for r in rs)
        reserved = sum(u["reserved"] for u in used)
        sold = sum(u["sold"] for u in used)
        data = {
            "item_id": item.item_id,
            "name": item.name,
            "image_url": item.image_url,
            "memo": item.memo,
            "total_received": total,
            "reserved": reserved,
            "sold": sold,
            "available": total - reserved - sold,
            "avg_unit_cost": average_cost(rs),
            "last_received_at": max((r.received_at for r in rs), default=None),
        }
        if with_detail:
            data["receipts"] = sorted(rs, key=lambda r: (r.received_at, r.receipt_id), reverse=True)
            data["allocations"] = [
                {k: u[k] for k in ("product_type", "product_id", "product_name", "reserved", "sold")} for u in used
            ]
        result.append(data)
    return result


def get_items(db: Session) -> list[dict]:
    items = db.query(InventoryItem).order_by(InventoryItem.created_at.desc(), InventoryItem.item_id.desc()).all()
    return _summaries(db, items)


def get_item_detail(db: Session, item_id: int) -> Optional[dict]:
    item = db.get(InventoryItem, item_id)
    return _summaries(db, [item], with_detail=True)[0] if item else None


def _lock_item_summary(db: Session, item_id: int) -> dict:
    # 같은 품목으로 동시에 상품을 올려도 재고보다 많이 묶이지 않게 품목 행을 잠근다
    item = db.query(InventoryItem).filter(InventoryItem.item_id == item_id).with_for_update().first()
    if not item:
        raise InventoryError("재고 품목을 찾을 수 없습니다")
    return _summaries(db, [item])[0]


# 상품 등록과 같은 트랜잭션에서 호출한다 (commit은 호출한 쪽에서).
# needs: [(item_id, 묶을 수량)] — 같은 품목이 여러 줄이면 합쳐서 검사한다
def check_available(db: Session, needs: list[tuple[int, int]]) -> None:
    totals: dict[int, int] = defaultdict(int)
    for item_id, qty in needs:
        totals[item_id] += qty
    for item_id in sorted(totals):
        s = _lock_item_summary(db, item_id)
        if totals[item_id] > s["available"]:
            raise InventoryError(f"'{s['name']}' 재고가 {s['available']}개뿐이라 {totals[item_id]}개를 올릴 수 없습니다")


def add_link(db: Session, item_id: int, product_type: str, product_id: int) -> None:
    db.add(InventoryLink(item_id=item_id, product_type=product_type, product_id=product_id))
    db.flush()


def get_link(db: Session, product_type: str, product_id: int) -> Optional[InventoryLink]:
    return db.query(InventoryLink).filter(InventoryLink.product_type == product_type, InventoryLink.product_id == product_id).first()


# 상점 수량 조정 — 늘리면 늘린 만큼 재고가 있어야 한다 (상품 행은 호출한 쪽에서 잠근다)
def check_store_stock_increase(db: Session, store_product_id: int, delta: int) -> None:
    if delta <= 0:
        return
    link = get_link(db, "store", store_product_id)
    if not link:
        return
    s = _lock_item_summary(db, link.item_id)
    if delta > s["available"]:
        raise InventoryError(f"재고가 {s['available']}개뿐이라 {delta}개를 더 올릴 수 없습니다")


def get_item_for_product(db: Session, product_type: str, product_id: int) -> Optional[dict]:
    link = get_link(db, product_type, product_id)
    if not link:
        return None
    return _summaries(db, [db.get(InventoryItem, link.item_id)])[0]


# ── 입고 ──

def create_receipt(
    db: Session,
    item_id: Optional[int],
    name: Optional[str],
    image_url: Optional[str],
    quantity: int,
    unit_cost: int,
    received_at: date,
    supplier: Optional[str],
    memo: Optional[str],
) -> int:
    if item_id is None:
        item = InventoryItem(name=name, image_url=image_url)
        db.add(item)
        db.flush()
        item_id = item.item_id
    elif not db.get(InventoryItem, item_id):
        raise InventoryError("재고 품목을 찾을 수 없습니다")
    db.add(InventoryReceipt(
        item_id=item_id, quantity=quantity, unit_cost=unit_cost, received_at=received_at, supplier=supplier, memo=memo,
    ))
    db.commit()
    return item_id


# 입고 기록을 고치거나 지울 때 이미 상품에 올렸거나 팔린 수량보다 입고 합계가 적어지면 안 된다
def _check_receipt_change(db: Session, receipt: InventoryReceipt, next_quantity: int) -> None:
    s = _lock_item_summary(db, receipt.item_id)
    used = s["reserved"] + s["sold"]
    if s["total_received"] - receipt.quantity + next_quantity < used:
        raise InventoryError(f"이 품목은 이미 {used}개를 상품에 올렸거나 팔았어요. 입고 합계가 {used}개보다 적어질 수 없습니다")


def update_receipt(db: Session, receipt_id: int, changes: dict) -> Optional[InventoryReceipt]:
    receipt = db.query(InventoryReceipt).filter(InventoryReceipt.receipt_id == receipt_id).with_for_update().first()
    if not receipt:
        return None
    if "quantity" in changes:
        _check_receipt_change(db, receipt, changes["quantity"])
    for key, value in changes.items():
        setattr(receipt, key, value)
    db.commit()
    db.refresh(receipt)
    return receipt


def delete_receipt(db: Session, receipt_id: int) -> bool:
    receipt = db.query(InventoryReceipt).filter(InventoryReceipt.receipt_id == receipt_id).with_for_update().first()
    if not receipt:
        return False
    _check_receipt_change(db, receipt, 0)
    item_id = receipt.item_id
    db.delete(receipt)
    db.flush()
    # 입고가 하나도 안 남고 어디에도 안 쓴 품목이면 품목도 지운다
    left = db.query(InventoryReceipt.receipt_id).filter(InventoryReceipt.item_id == item_id).first()
    used = db.query(InventoryLink.link_id).filter(InventoryLink.item_id == item_id).first()
    if not left and not used:
        db.query(InventoryItem).filter(InventoryItem.item_id == item_id).delete()
    db.commit()
    return True


# 손익 계산용 — 품목별 평균 원가와 상품 → 품목 연결
def get_avg_costs(db: Session) -> dict[int, int]:
    receipts: dict[int, list[InventoryReceipt]] = defaultdict(list)
    for r in db.query(InventoryReceipt):
        receipts[r.item_id].append(r)
    return {item_id: average_cost(rs) for item_id, rs in receipts.items()}


def get_link_map(db: Session) -> dict[tuple[str, int], int]:
    return {(l.product_type, l.product_id): l.item_id for l in db.query(InventoryLink)}


def get_purchases_total(db: Session, start: date, end: date) -> int:
    total = (
        db.query(func.sum(InventoryReceipt.quantity * InventoryReceipt.unit_cost))
        .filter(InventoryReceipt.received_at >= start, InventoryReceipt.received_at <= end)
        .scalar()
    )
    return int(total or 0)
