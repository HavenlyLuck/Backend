import logging
from sqlalchemy import or_
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.models.storage import StorageItem
from app.models.raffle import RaffleProduct, RaffleEntry
from app.models.store import StoreProduct
from app.models.kuji import KujiSet, KujiPrize
from app.models.payment import Payment
from app.models.user import User
from app.models.address import ShippingAddress
from app.models.free_ticket import FreeTicket
from app.crud import point as point_crud
from app.crud import address as address_crud
from app.crud import alimtalk as alimtalk_crud


class StorageCancelError(Exception):
    pass


# 배송 신청할 수 없는 경우 (보관함에 없음 · 이미 신청됨 · 배송지 없음)
class ShippingRequestError(Exception):
    pass


# 보관 기한 — 응모 당첨·쿠지 상품은 보관함에 들어온 날부터 이 기간 안에 배송 신청하지 않으면 쌀 응모권으로 바뀐다.
# 상점에서 산 상품은 대상이 아니다. 프론트 lib/storageExpiry.ts와 값이 같아야 한다
STORAGE_KEEP_DAYS = 30
CONVERT_WON_PER_TICKET = 2000   # 상품 가치 2,000원당 쌀 응모권 1장
KUJI_COST_MARKUP_PERCENT = 130  # 쿠지 상품은 정가가 없어 원가 × 1.3을 가치로 본다
CONVERT_BATCH = 100


def _ceil_div(a: int, b: int) -> int:
    return -(-a // b)


# 바뀔 쌀 응모권 장수 — 응모: 정가 ÷ 2,000원(올림), 쿠지 상 · 라스트원상: 원가 × 1.3 ÷ 2,000원(올림, 1개당) × 개수.
# 원가는 등록 상품의 매입 평균 단가(없으면 쿠지 등록 때 적은 원가). 값을 알 수 없어도 최소 1장은 준다
def convert_tickets(item: StorageItem, raffle: Optional[RaffleProduct], kuji: Optional[KujiSet],
                    prize: Optional[KujiPrize], costs: dict[int, int], links: dict) -> Optional[int]:
    if item.source == "raffle":
        price = raffle.price_krw if raffle else 0
        return max(1, _ceil_div(price, CONVERT_WON_PER_TICKET))
    if item.source != "kuji":
        return None
    if prize is not None:
        catalog = prize.catalog_item_id or links.get(("kuji_prize", prize.kuji_prize_id))
        cost = costs.get(catalog) or prize.cost or 0
    else:
        catalog = (kuji.last_one_catalog_item_id if kuji else None) or (links.get(("kuji_last_one", kuji.kuji_set_id)) if kuji else None)
        cost = costs.get(catalog) or (kuji.last_one_cost if kuji else 0) or 0
    per_unit = max(1, _ceil_div(cost * KUJI_COST_MARKUP_PERCENT, 100 * CONVERT_WON_PER_TICKET))
    return per_unit * item.quantity


# 쿠지 상품의 원가 계산에 필요한 등록 상품 평균 단가 · 예전 재고 연결
def _kuji_cost_info(db: Session, kujis, prizes) -> tuple[dict[int, int], dict]:
    from app.crud import inventory as inventory_crud   # 순환 import 피하기
    links = inventory_crud.get_link_map(db)
    ids = [p.catalog_item_id or links.get(("kuji_prize", p.kuji_prize_id)) for p in prizes if p]
    ids += [k.last_one_catalog_item_id or links.get(("kuji_last_one", k.kuji_set_id)) for k in kujis if k]
    return inventory_crud.get_purchase_avg_costs(db, ids), links


# 추첨 결과 저장과 같은 트랜잭션에서 호출한다 (commit은 호출한 쪽에서)
def add_raffle_win(db: Session, user_id: int, raffle_product_id: int) -> StorageItem:
    item = StorageItem(
        user_id=user_id,
        source="raffle",
        raffle_product_id=raffle_product_id,
        quantity=1,
    )
    db.add(item)
    db.flush()
    return item


# 상점 구매와 같은 트랜잭션에서 호출한다 (commit은 호출한 쪽에서)
def add_store_purchase(
    db: Session, user_id: int, store_product_id: int, quantity: int, amount_spent: int, payment_id: Optional[str] = None,
) -> StorageItem:
    item = StorageItem(
        user_id=user_id,
        source="store",
        store_product_id=store_product_id,
        quantity=quantity,
        amount_spent=amount_spent,
        payment_id=payment_id,
    )
    db.add(item)
    db.flush()
    return item


# 쿠지 뽑기와 같은 트랜잭션에서 호출한다 (commit은 호출한 쪽에서)
# 라스트원상은 kuji_prize_id 없이 kuji_set_id만 남긴다
def add_kuji_win(
    db: Session, user_id: int, kuji_set_id: int, kuji_prize_id: Optional[int], quantity: int, amount_spent: Optional[int],
    payment_id: Optional[str] = None,
) -> StorageItem:
    item = StorageItem(
        user_id=user_id,
        source="kuji",
        kuji_set_id=kuji_set_id,
        kuji_prize_id=kuji_prize_id,
        quantity=quantity,
        amount_spent=amount_spent,
        payment_id=payment_id,
    )
    db.add(item)
    db.flush()
    return item


def _kuji_item_name(kuji: Optional[KujiSet], prize: Optional[KujiPrize]) -> tuple[str, Optional[str]]:
    if not kuji:
        return "(삭제된 상품)", None
    if prize:
        return f"{kuji.title} {prize.grade}상 - {prize.name}", prize.image_url or kuji.image_url
    return f"{kuji.title} 라스트원상 - {kuji.last_one_name}", kuji.last_one_image_url or kuji.image_url


def _storage_query(db: Session, *extra):
    return (
        db.query(StorageItem, RaffleProduct, StoreProduct, KujiSet, KujiPrize, *extra)
        .outerjoin(RaffleProduct, StorageItem.raffle_product_id == RaffleProduct.raffle_product_id)
        .outerjoin(StoreProduct, StorageItem.store_product_id == StoreProduct.store_product_id)
        .outerjoin(KujiSet, StorageItem.kuji_set_id == KujiSet.kuji_set_id)
        .outerjoin(KujiPrize, StorageItem.kuji_prize_id == KujiPrize.kuji_prize_id)
    )


# 보관함 상품 1건 — 당첨/구매 상품 정보를 붙인다
def _item_dict(item, raffle, store, kuji, prize) -> dict:
    product = raffle or store
    if item.source == "kuji":
        name, image_url = _kuji_item_name(kuji, prize)
    else:
        name = product.product_name if product else "(삭제된 상품)"
        image_url = product.image_url if product else None
    return {
        "storage_item_id": item.storage_item_id,
        "source": item.source,
        "raffle_product_id": item.raffle_product_id,
        "store_product_id": item.store_product_id,
        "kuji_set_id": item.kuji_set_id,
        "kuji_prize_id": item.kuji_prize_id,
        "product_name": name,
        "image_url": image_url,
        "quantity": item.quantity,
        "price_krw": raffle.price_krw if raffle else None,
        "pay_type": store.pay_type if store else ("cash" if item.source == "kuji" and item.amount_spent else None),
        "amount_spent": item.amount_spent,
        "status": item.status,
        "address_id": item.address_id,
        "shipping_payment_id": item.shipping_payment_id,
        "requested_at": item.requested_at,
        "created_at": item.created_at,
        "carrier": item.carrier,
        "tracking_number": item.tracking_number,
        "shipped_at": item.shipped_at,
        "delivered_at": item.delivered_at,
    }


# 내 보관함 — 최신순.
# 응모 당첨 상품은 당첨자가 추첨 결과를 확인한 뒤(raffle_entries.result_checked_at)부터 보여준다 —
# 결과 화면보다 보관함에서 먼저 당첨을 알게 되지 않게
def get_user_storage_items(db: Session, user_id: int) -> list[dict]:
    result_checked = (
        db.query(RaffleEntry.entry_id)
        .filter(
            RaffleEntry.raffle_product_id == StorageItem.raffle_product_id,
            RaffleEntry.user_id == user_id,
            RaffleEntry.result_checked_at.isnot(None),
        )
        .exists()
    )
    rows = (
        _storage_query(db)
        .filter(StorageItem.user_id == user_id, StorageItem.status != "converted")
        .filter(or_(StorageItem.source != "raffle", result_checked))
        .order_by(StorageItem.created_at.desc(), StorageItem.storage_item_id.desc())
        .all()
    )
    kuji_rows = [r for r in rows if r[0].source == "kuji"]
    costs, links = _kuji_cost_info(db, [r[3] for r in kuji_rows], [r[4] for r in kuji_rows]) if kuji_rows else ({}, {})
    return [
        {**_item_dict(*row), "convert_tickets": convert_tickets(row[0], row[1], row[3], row[4], costs, links)}
        for row in rows
    ]


# 관리자 배송 관리 — 배송 신청(requested) / 발송 완료(shipped)된 상품 + 신청한 사람 · 배송지.
# 배송지는 고객이 나중에 지웠어도(deleted_at) 신청 당시 주소로 보내야 하므로 그대로 붙인다
def get_admin_shipping_items(db: Session, status: str) -> list[dict]:
    rows = (
        _storage_query(db, User, ShippingAddress)
        .join(User, StorageItem.user_id == User.user_id)
        .outerjoin(ShippingAddress, StorageItem.address_id == ShippingAddress.address_id)
        .filter(StorageItem.status == status)
        .order_by(StorageItem.requested_at.asc(), StorageItem.storage_item_id.asc())
        .all()
    )
    result = []
    for item, raffle, store, kuji, prize, user, addr in rows:
        data = _item_dict(item, raffle, store, kuji, prize)
        data["user_id"] = user.user_id
        data["nickname"] = user.nickname
        data["address"] = {
            "recipient": addr.recipient,
            "phone": addr.phone,
            "zip_code": addr.zip_code,
            "address1": addr.address1,
            "address2": addr.address2,
        } if addr else None
        result.append(data)
    return result


def get_items_for_update(db: Session, storage_item_ids: list[int]) -> list[StorageItem]:
    return (
        db.query(StorageItem)
        .filter(StorageItem.storage_item_id.in_(storage_item_ids))
        .with_for_update()
        .all()
    )


def mark_shipped(db: Session, items: list[StorageItem], carrier: str, tracking_number: str) -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for item in items:
        item.status = "shipped"
        item.carrier = carrier
        item.tracking_number = tracking_number
        item.shipped_at = now
    # 받는 회원마다 택배 발송 알림톡 (보통 한 박스 = 한 회원)
    names = {
        row[0].storage_item_id: _item_dict(*row)["product_name"]
        for row in _storage_query(db).filter(StorageItem.storage_item_id.in_([i.storage_item_id for i in items]))
    }
    by_user: dict[int, list[StorageItem]] = {}
    for item in sorted(items, key=lambda i: i.storage_item_id):
        by_user.setdefault(item.user_id, []).append(item)
    for user_id, user_items in by_user.items():
        alimtalk_crud.enqueue_shipped(
            db, user_id, user_items[0].storage_item_id,
            [names.get(i.storage_item_id, "주문 상품") for i in user_items], carrier, tracking_number,
        )
    db.commit()


def get_user_items_for_update(db: Session, user_id: int, storage_item_ids: list[int]) -> list[StorageItem]:
    return (
        db.query(StorageItem)
        .filter(StorageItem.user_id == user_id, StorageItem.storage_item_id.in_(storage_item_ids))
        .with_for_update()
        .all()
    )


# 배송 신청할 수 있는지 확인 — 보관 중(ready)인 내 상품 + 내 배송지. 확인한 상품들을 잠근 채로 돌려준다
def _check_shipping(db: Session, user_id: int, storage_item_ids: list[int], address_id: int) -> list[StorageItem]:
    ids = set(storage_item_ids)
    if not ids:
        raise ShippingRequestError("배송 신청할 상품을 선택해주세요")
    if not address_crud.get_user_address(db, user_id, address_id):
        raise LookupError("배송지를 찾을 수 없습니다")
    items = get_user_items_for_update(db, user_id, list(ids))
    if len(items) != len(ids):
        raise LookupError("보관함에 없는 상품이 포함되어 있습니다")
    if any(item.status != "ready" for item in items):
        raise ShippingRequestError("이미 배송 신청된 상품이 포함되어 있습니다")
    return items


# 배송비 결제창을 열기 전 확인 (결제 후 fulfill_shipping에서 다시 확인한다)
def check_can_request_shipping(db: Session, user_id: int, storage_item_ids: list[int], address_id: int) -> int:
    try:
        return len(_check_shipping(db, user_id, storage_item_ids, address_id))
    finally:
        db.rollback()   # 확인만 하고 잠금을 푼다


# 배송비 결제 확인 후 배송 신청 접수 — 결제 완료 처리와 같은 트랜잭션에서 호출한다 (commit은 호출한 쪽에서).
# 그 사이 다른 결제로 이미 신청됐거나 배송지를 지웠으면 ShippingRequestError/LookupError → 결제를 환불한다
def fulfill_shipping(db: Session, user_id: int, storage_item_ids: list[int], address_id: int, payment_id: str) -> list[StorageItem]:
    items = _check_shipping(db, user_id, storage_item_ids, address_id)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for item in items:
        item.status = "requested"
        item.address_id = address_id
        item.requested_at = now
        item.shipping_payment_id = payment_id
    db.flush()
    return items


# 배송 신청 취소 — 발송 전(requested)에만. 같은 배송비로 같이 신청한 상품은 한 박스라 함께 취소되고 보관 중으로 돌아간다.
# 배송비 결제는 cancel_requested로 바꿔 둔다. commit 후 호출한 쪽이 포트원 환불을 요청한다 (실패하면 주기 작업이 다시 시도)
# 반환: 환불 요청할 payment_id (배송비 없이 신청됐던 예전 신청이면 None)
def cancel_shipping(db: Session, user_id: int, storage_item_id: int) -> Optional[str]:
    item = (
        db.query(StorageItem)
        .filter(StorageItem.storage_item_id == storage_item_id, StorageItem.user_id == user_id)
        .with_for_update()
        .first()
    )
    if not item:
        raise LookupError("보관함에 없는 상품입니다")
    if item.status == "shipped":
        raise StorageCancelError("이미 발송된 상품은 배송 신청을 취소할 수 없습니다")
    if item.status != "requested":
        raise StorageCancelError("배송 신청한 상품이 아닙니다")

    payment = None
    items = [item]
    if item.shipping_payment_id:
        payment = (
            db.query(Payment)
            .filter(Payment.payment_id == item.shipping_payment_id, Payment.user_id == user_id)
            .with_for_update()
            .first()
        )
        if not payment or payment.status != "paid":
            raise StorageCancelError("환불할 수 없는 배송비 결제입니다. 고객센터로 문의해주세요")
        items = (
            db.query(StorageItem)
            .filter(StorageItem.shipping_payment_id == payment.payment_id)
            .with_for_update()
            .all()
        )
        # 관리자가 일부만 먼저 발송했으면 배송비를 돌려줄 수 없다
        if any(i.status != "requested" for i in items):
            raise StorageCancelError("함께 신청한 상품 중 이미 발송된 상품이 있어 취소할 수 없습니다. 고객센터로 문의해주세요")
        payment.status = "cancel_requested"
        payment.cancel_reason = "배송 신청 취소"

    for i in items:
        i.status = "ready"
        i.address_id = None
        i.requested_at = None
        i.shipping_payment_id = None
    db.commit()
    return payment.payment_id if payment else None


# 보관함에서 상점 구매 취소 — 배송 신청 전(ready)인 카드 결제 상점 구매만 가능 (쌀포인트 구매는 취소 불가).
# 재고를 되돌리고 보관함에서 빼고, 결제는 cancel_requested로 바꿔 둔다.
# commit 후 호출한 쪽이 포트원 환불을 요청한다 (실패하면 주기 작업이 다시 시도)
# 반환: 환불 요청할 payment_id
def cancel_store_purchase(db: Session, user_id: int, storage_item_id: int) -> str:
    item = (
        db.query(StorageItem)
        .filter(StorageItem.storage_item_id == storage_item_id, StorageItem.user_id == user_id)
        .with_for_update()
        .first()
    )
    if not item:
        raise LookupError("보관함에 없는 상품입니다")
    if item.source != "store":
        raise StorageCancelError("상점에서 구매한 상품만 구매 취소할 수 있습니다")
    if item.status != "ready":
        raise StorageCancelError("배송 신청한 상품은 구매 취소할 수 없습니다")

    product = (
        db.query(StoreProduct)
        .filter(StoreProduct.store_product_id == item.store_product_id)
        .with_for_update()
        .first()
    )
    if not product:
        raise StorageCancelError("구매 취소할 수 없는 상품입니다")
    if product.pay_type != "cash":
        raise StorageCancelError("쌀포인트로 구매한 상품은 구매 취소할 수 없습니다")

    payment = (
        db.query(Payment).filter(Payment.payment_id == item.payment_id).with_for_update().first()
        if item.payment_id else None
    )
    if not payment or payment.status != "paid":
        raise StorageCancelError("구매 취소할 수 없는 결제입니다")
    payment.status = "cancel_requested"
    payment.cancel_reason = "보관함에서 구매 취소"
    if payment.point_used:
        # 할인에 쓴 쌀포인트는 카드 환불과 함께 바로 돌려준다
        point_crud.apply_point_change(
            db, user_id, payment.point_used, "store_discount_refund",
            reference_id=item.storage_item_id,
            description=f"{product.product_name} 구매 취소 — 할인 쌀포인트 반환"[:255],
        )

    if product.sale_mode != "regular":   # 일반 상품은 개수가 없어 되돌리지 않는다
        product.stock += item.quantity
    db.delete(item)
    db.commit()
    return payment.payment_id


# 이 사람이 이 송장으로 받은 상품 (배송 조회 권한 확인용)
def get_user_items_by_tracking(db: Session, user_id: int, carrier: str, tracking_number: str) -> list[StorageItem]:
    return (
        db.query(StorageItem)
        .filter(
            StorageItem.user_id == user_id,
            StorageItem.status == "shipped",
            StorageItem.carrier == carrier,
            StorageItem.tracking_number == tracking_number,
        )
        .all()
    )


# 배송 조회에서 배송완료가 확인되면 같은 송장으로 나간 상품을 모두 배송 완료로 표시한다
def mark_delivered(db: Session, items: list[StorageItem]) -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    changed = False
    for item in items:
        if item.delivered_at is None:
            item.delivered_at = now
            changed = True
    if changed:
        db.commit()


# 보관 기한이 지난 응모 당첨·쿠지 상품을 쌀 응모권으로 바꾼다 — 서버 주기 작업(app/main.py)이 1시간마다 부른다.
# 배송 신청 전(ready)인 것만. 보관함 행을 잠그고 ready인 것만 바꾸므로 서버가 여러 개여도 한 번만 바뀐다.
# 바뀐 응모권은 보관함의 쌀 응모권(free_tickets, kind=storage_convert)으로 들어간다. 반환: 바꾼 상품 수
def convert_expired_items(db: Session) -> int:
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=STORAGE_KEEP_DAYS)
    total = 0
    while True:
        items = (
            db.query(StorageItem)
            .filter(
                StorageItem.status == "ready",
                StorageItem.source.in_(["raffle", "kuji"]),
                StorageItem.created_at <= cutoff,
            )
            .order_by(StorageItem.storage_item_id)
            .limit(CONVERT_BATCH)
            .with_for_update()
            .all()
        )
        if not items:
            db.rollback()
            return total
        raffle_ids = {i.raffle_product_id for i in items if i.raffle_product_id}
        kuji_ids = {i.kuji_set_id for i in items if i.kuji_set_id}
        prize_ids = {i.kuji_prize_id for i in items if i.kuji_prize_id}
        raffles = {r.raffle_product_id: r for r in db.query(RaffleProduct).filter(RaffleProduct.raffle_product_id.in_(raffle_ids))} if raffle_ids else {}
        kujis = {k.kuji_set_id: k for k in db.query(KujiSet).filter(KujiSet.kuji_set_id.in_(kuji_ids))} if kuji_ids else {}
        prizes = {p.kuji_prize_id: p for p in db.query(KujiPrize).filter(KujiPrize.kuji_prize_id.in_(prize_ids))} if prize_ids else {}
        costs, links = _kuji_cost_info(db, kujis.values(), prizes.values()) if kujis else ({}, {})
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        for item in items:
            n = convert_tickets(item, raffles.get(item.raffle_product_id), kujis.get(item.kuji_set_id),
                                prizes.get(item.kuji_prize_id), costs, links) or 1
            db.add_all(FreeTicket(user_id=item.user_id, kind="storage_convert", created_at=now) for _ in range(n))
            item.status = "converted"
            item.converted_at = now
            item.convert_tickets = n
        db.commit()
        total += len(items)
        logging.info("storage items converted to ssal tickets: %d", len(items))
