from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import func, or_
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


# 상품 등록 때 품목만 만들려고 넣는 빈 입고 기록 (프론트 lib/catalog.ts) — 입고 수량 · 평균 단가에 넣지 않는다
PLACEHOLDER_MEMO = "상품 등록 (재고 아님)"


def is_placeholder(r: InventoryReceipt) -> bool:
    return r.memo == PLACEHOLDER_MEMO and r.unit_cost == 0 and r.quantity == 1


# 상품이 어느 등록 상품(품목)인지 — 상품에 저장한 catalog_item_id가 먼저, 없으면 예전 방식 inventory_links.
# 장부(crud/ledger.py)와 같은 기준이다. 한 상품은 한 품목에만 들어가서 두 번 세지 않는다
def _owner(catalog_item_id: Optional[int], link_map: dict, product_type: str, product_id: int) -> Optional[int]:
    return catalog_item_id or link_map.get((product_type, product_id))


def _converted(db: Session, column, ids, *extra) -> dict[int, int]:
    """보관 기한이 지나 쌀 응모권으로 바뀐 보관함 수량 (물건이 회사에 남는다) — column 값별 합계"""
    if not ids:
        return {}
    return {
        k: int(n or 0) for k, n in db.query(column, func.sum(StorageItem.quantity))
        .filter(column.in_(ids), StorageItem.status == "converted", *extra)
        .group_by(column)
    }


def _product_usage(db: Session, item_ids) -> dict[int, list[dict]]:
    """품목 id → 그 품목으로 올린 상품들의 [{reserved, sold, product_type(raffle|kuji|store), product_id, product_name}]

    sold(나간 수)는 장부 outflows 합계와 같다 — 응모 당첨 1 · 쿠지 실물 상 뽑힌 수 · 라스트원 1 · 상점 보관함 수량에서
    보관 기한이 지나 쌀 응모권으로 바뀐 것을 뺀다 (보관함에서 구매 취소한 상품은 보관함 행이 지워져 이미 빠져 있다).
    reserved(판매 중)는 진행 중인 응모 1 · 진행 중인 쿠지 판의 남은 실물 상 · 한정 상점 상품의 stock. 일반 판매는 0
    """
    ids = {i for i in item_ids if i is not None}
    out: dict[int, list[dict]] = defaultdict(list)
    if not ids:
        return out
    link_map: dict[tuple[str, int], int] = {}
    linked: dict[str, set[int]] = defaultdict(set)
    for l in db.query(InventoryLink).filter(InventoryLink.item_id.in_(ids)):
        link_map.setdefault((l.product_type, l.product_id), l.item_id)
        linked[l.product_type].add(l.product_id)

    # 응모
    raffles = []
    for r in db.query(RaffleProduct).filter(or_(
        RaffleProduct.catalog_item_id.in_(ids), RaffleProduct.raffle_product_id.in_(linked["raffle"]),
    )):
        owner = _owner(r.catalog_item_id, link_map, "raffle", r.raffle_product_id)
        if owner in ids:
            raffles.append((owner, r))
    conv = _converted(db, StorageItem.raffle_product_id, [r.raffle_product_id for _, r in raffles], StorageItem.source == "raffle")
    for owner, r in raffles:
        out[owner].append({
            "reserved": 1 if r.status in ("open", "funding") else 0,
            "sold": (1 if r.status == "completed" else 0) - conv.get(r.raffle_product_id, 0),
            "product_type": "raffle", "product_id": r.raffle_product_id,
            "product_name": f"[응모] {r.product_name}",
        })

    # 상점 (카드 · 쌀포인트) — 보관함에 들어간 수량이 팔린 수량
    stores = []
    for p in db.query(StoreProduct).filter(or_(
        StoreProduct.catalog_item_id.in_(ids), StoreProduct.store_product_id.in_(linked["store"]),
    )):
        owner = _owner(p.catalog_item_id, link_map, "store", p.store_product_id)
        if owner in ids:
            stores.append((owner, p))
    store_ids = [p.store_product_id for _, p in stores]
    sold = {
        k: int(n or 0) for k, n in db.query(StorageItem.store_product_id, func.sum(StorageItem.quantity))
        .filter(StorageItem.store_product_id.in_(store_ids), StorageItem.source == "store", StorageItem.status != "converted")
        .group_by(StorageItem.store_product_id)
    } if store_ids else {}
    for owner, p in stores:
        label = "[상점]" if p.pay_type == "cash" else "[쌀포인트 상점]"
        out[owner].append({
            "reserved": 0 if p.sale_mode == "regular" or p.deleted_at is not None else p.stock,
            "sold": sold.get(p.store_product_id, 0),
            "product_type": "store", "product_id": p.store_product_id,
            "product_name": f"{label} {p.product_name}",
        })

    # 쿠지 실물 상 (쌀포인트 상은 실물이 아니라 뺀다)
    prizes = []
    for prize, kuji in (
        db.query(KujiPrize, KujiSet).join(KujiSet, KujiPrize.kuji_set_id == KujiSet.kuji_set_id)
        .filter(or_(KujiPrize.catalog_item_id.in_(ids), KujiPrize.kuji_prize_id.in_(linked["kuji_prize"])))
    ):
        owner = _owner(prize.catalog_item_id, link_map, "kuji_prize", prize.kuji_prize_id)
        if owner in ids and not prize.point_amount:
            prizes.append((owner, prize, kuji))
    conv = _converted(db, StorageItem.kuji_prize_id, [p.kuji_prize_id for _, p, _ in prizes])
    for owner, prize, kuji in prizes:
        out[owner].append({
            # 판매 종료된 쿠지의 안 뽑힌 상품은 재고로 돌아간다
            "reserved": prize.remaining_quantity if kuji.status != "closed" else 0,
            "sold": prize.quantity - prize.remaining_quantity - conv.get(prize.kuji_prize_id, 0),
            "product_type": "kuji", "product_id": kuji.kuji_set_id,
            "product_name": f"[쿠지] {kuji.title} {prize.grade}상",
        })

    # 쿠지 라스트원상
    last_ones = []
    for k in db.query(KujiSet).filter(
        KujiSet.last_one_name.isnot(None),
        or_(KujiSet.last_one_catalog_item_id.in_(ids), KujiSet.kuji_set_id.in_(linked["kuji_last_one"])),
    ):
        owner = _owner(k.last_one_catalog_item_id, link_map, "kuji_last_one", k.kuji_set_id)
        if owner in ids:
            last_ones.append((owner, k))
    conv = _converted(db, StorageItem.kuji_set_id, [k.kuji_set_id for _, k in last_ones],
                      StorageItem.source == "kuji", StorageItem.kuji_prize_id.is_(None))
    for owner, k in last_ones:
        won = k.last_one_user_id is not None
        out[owner].append({
            "reserved": 1 if not won and k.status != "closed" else 0,
            "sold": (1 if won else 0) - conv.get(k.kuji_set_id, 0),
            "product_type": "kuji", "product_id": k.kuji_set_id,
            "product_name": f"[쿠지] {k.title} 라스트원상",
        })
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
    usage = _product_usage(db, ids)

    result = []
    for item in items:
        rs = receipts[item.item_id]
        bought = [r for r in rs if not is_placeholder(r)]   # 등록용 빈 기록은 입고로 세지 않는다
        used = usage[item.item_id]
        total = sum(r.quantity for r in bought)
        reserved = sum(u["reserved"] for u in used)
        sold = sum(u["sold"] for u in used)
        data = {
            "item_id": item.item_id,
            "name": item.name,
            "image_url": item.image_url,
            "memo": item.memo,
            "description": item.description,
            "total_received": total,
            "reserved": reserved,
            "sold": sold,
            # 자르지 않는다 — 일반 판매는 재고가 없어도 주문을 받으므로 모자란 만큼 음수로 보인다
            "available": total - reserved - sold,
            "avg_unit_cost": average_cost(bought),
            "last_received_at": max((r.received_at for r in bought), default=None),
        }
        if with_detail:
            data["receipts"] = sorted(rs, key=lambda r: (r.received_at, r.receipt_id), reverse=True)
            data["allocations"] = [
                {k: u[k] for k in ("product_type", "product_id", "product_name", "reserved", "sold")} for u in used
            ]
        result.append(data)
    return result


def _active_item(db: Session, item_id: int) -> Optional[InventoryItem]:
    return db.query(InventoryItem).filter(InventoryItem.item_id == item_id, InventoryItem.deleted_at.is_(None)).first()


# 게시할 때 고른 등록 상품이 있는지 — 재고 확인·묶기 없이 연결만 하므로 존재만 본다 (지운 상품도 허용)
def check_catalog_items(db: Session, item_ids) -> None:
    ids = {i for i in item_ids if i is not None}
    if not ids:
        return
    found = {i for (i,) in db.query(InventoryItem.item_id).filter(InventoryItem.item_id.in_(ids))}
    if ids - found:
        raise InventoryError("등록 상품을 찾을 수 없습니다")


def get_items(db: Session) -> list[dict]:
    items = db.query(InventoryItem).filter(InventoryItem.deleted_at.is_(None)).order_by(InventoryItem.created_at.desc(), InventoryItem.item_id.desc()).all()
    return _summaries(db, items)


def get_item_detail(db: Session, item_id: int) -> Optional[dict]:
    item = _active_item(db, item_id)
    return _summaries(db, [item], with_detail=True)[0] if item else None


def _lock_item_summary(db: Session, item_id: int) -> dict:
    # 같은 품목으로 동시에 상품을 올려도 재고보다 많이 묶이지 않게 품목 행을 잠근다
    item = (
        db.query(InventoryItem)
        .filter(InventoryItem.item_id == item_id, InventoryItem.deleted_at.is_(None))
        .with_for_update()
        .first()
    )
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
    # 상품에 저장한 등록 상품(catalog_item_id)이 먼저, 없으면 예전 재고 연결
    catalog_id = None
    if product_type == "raffle":
        catalog_id = db.query(RaffleProduct.catalog_item_id).filter(RaffleProduct.raffle_product_id == product_id).scalar()
    elif product_type == "store":
        catalog_id = db.query(StoreProduct.catalog_item_id).filter(StoreProduct.store_product_id == product_id).scalar()
    elif product_type == "kuji_prize":
        catalog_id = db.query(KujiPrize.catalog_item_id).filter(KujiPrize.kuji_prize_id == product_id).scalar()
    elif product_type == "kuji_last_one":
        catalog_id = db.query(KujiSet.last_one_catalog_item_id).filter(KujiSet.kuji_set_id == product_id).scalar()
    if catalog_id is None:
        link = get_link(db, product_type, product_id)
        catalog_id = link.item_id if link else None
    item = db.get(InventoryItem, catalog_id) if catalog_id is not None else None
    return _summaries(db, [item])[0] if item else None


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
    description: Optional[str] = None,
    tax_free: bool = False,
) -> int:
    if item_id is None:
        item = InventoryItem(name=name, image_url=image_url, description=description)
        db.add(item)
        db.flush()
        item_id = item.item_id
    elif not _active_item(db, item_id):
        raise InventoryError("재고 품목을 찾을 수 없습니다")
    db.add(InventoryReceipt(
        item_id=item_id, quantity=quantity, unit_cost=unit_cost, received_at=received_at, supplier=supplier, memo=memo,
        tax_free=tax_free,
    ))
    db.commit()
    return item_id


# 상품 등록 — 입고 기록 없이 품목(이름 · 사진 · 설명)만 만든다
def create_item(db: Session, name: str, image_url: Optional[str], description: Optional[str]) -> int:
    item = InventoryItem(name=name, image_url=image_url, description=description)
    db.add(item)
    db.commit()
    return item.item_id


# 이름 · 설명 고치기 — changes에 들어 있는 칸만 바꾼다
def update_item(db: Session, item_id: int, changes: dict) -> bool:
    item = _active_item(db, item_id)
    if not item:
        return False
    for key, value in changes.items():
        setattr(item, key, value)
    db.commit()
    return True


# 상품 등록에서 지우기 — 목록에서만 숨긴다. 이미 게시한 상품은 내용을 복사해 갔으므로 그대로 남는다
def delete_item(db: Session, item_id: int) -> bool:
    item = _active_item(db, item_id)
    if not item:
        return False
    item.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    return True


# 입고 기록을 고치거나 지울 때 이미 상품에 올렸거나 팔린 수량보다 입고 합계가 적어지면 안 된다.
# next_quantity: 바꾼 뒤 이 기록이 입고 합계에 더하는 수량 (지우면 0). 등록용 빈 기록은 원래 0으로 센다
# 이미 모자란 품목(일반 판매로 재고보다 많이 판 경우)은 합계를 줄이는 것만 막는다
def _check_receipt_change(db: Session, receipt: InventoryReceipt, next_quantity: int) -> None:
    current = 0 if is_placeholder(receipt) else receipt.quantity
    if next_quantity >= current:
        return
    s = _lock_item_summary(db, receipt.item_id)
    used = s["reserved"] + s["sold"]
    if s["total_received"] - current + next_quantity < used:
        raise InventoryError(f"이 품목은 이미 {used}개를 상품에 올렸거나 팔았어요. 입고 합계가 {used}개보다 적어질 수 없습니다")


def update_receipt(db: Session, receipt_id: int, changes: dict) -> Optional[InventoryReceipt]:
    receipt = db.query(InventoryReceipt).filter(InventoryReceipt.receipt_id == receipt_id).with_for_update().first()
    if not receipt:
        return None
    if changes.keys() & {"quantity", "unit_cost", "memo"}:
        after = InventoryReceipt(
            quantity=changes.get("quantity", receipt.quantity),
            unit_cost=changes.get("unit_cost", receipt.unit_cost),
            memo=changes.get("memo", receipt.memo),
        )
        _check_receipt_change(db, receipt, 0 if is_placeholder(after) else after.quantity)
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


# 등록 상품별 매입 평균 단가 — 단가 0인 기록(등록 때 만든 빈 기록)은 뺀다. 매입 기록이 없으면 빠진다
def get_purchase_avg_costs(db: Session, item_ids) -> dict[int, int]:
    ids = {i for i in item_ids if i is not None}
    if not ids:
        return {}
    rows = (
        db.query(InventoryReceipt.item_id,
                 func.sum(InventoryReceipt.quantity * InventoryReceipt.unit_cost), func.sum(InventoryReceipt.quantity))
        .filter(InventoryReceipt.item_id.in_(ids), InventoryReceipt.unit_cost > 0, InventoryReceipt.quantity > 0)
        .group_by(InventoryReceipt.item_id)
        .all()
    )
    return {item_id: round(int(total) / int(qty)) for item_id, total, qty in rows if qty}


def get_link_map(db: Session) -> dict[tuple[str, int], int]:
    return {(l.product_type, l.product_id): l.item_id for l in db.query(InventoryLink)}


def get_purchases_total(db: Session, start: date, end: date) -> int:
    total = (
        db.query(func.sum(InventoryReceipt.quantity * InventoryReceipt.unit_cost))
        .filter(InventoryReceipt.received_at >= start, InventoryReceipt.received_at <= end)
        .scalar()
    )
    return int(total or 0)
