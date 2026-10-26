from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import Optional

from app.models.storage import StorageItem
from app.models.raffle import RaffleProduct
from app.models.store import StoreProduct
from app.models.kuji import KujiSet, KujiPrize
from app.models.payment import Payment
from app.models.user import User
from app.models.address import ShippingAddress


class StorageCancelError(Exception):
    pass


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
        "requested_at": item.requested_at,
        "created_at": item.created_at,
        "carrier": item.carrier,
        "tracking_number": item.tracking_number,
        "shipped_at": item.shipped_at,
    }


# 내 보관함 — 최신순
def get_user_storage_items(db: Session, user_id: int) -> list[dict]:
    rows = (
        _storage_query(db)
        .filter(StorageItem.user_id == user_id)
        .order_by(StorageItem.created_at.desc(), StorageItem.storage_item_id.desc())
        .all()
    )
    return [_item_dict(*row) for row in rows]


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
    db.commit()


def get_user_items_for_update(db: Session, user_id: int, storage_item_ids: list[int]) -> list[StorageItem]:
    return (
        db.query(StorageItem)
        .filter(StorageItem.user_id == user_id, StorageItem.storage_item_id.in_(storage_item_ids))
        .with_for_update()
        .all()
    )


def request_shipping(db: Session, items: list[StorageItem], address_id: int) -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for item in items:
        item.status = "requested"
        item.address_id = address_id
        item.requested_at = now
    db.commit()


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

    product.stock += item.quantity
    db.delete(item)
    db.commit()
    return payment.payment_id
