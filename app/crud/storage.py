from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import Optional

from app.models.storage import StorageItem
from app.models.raffle import RaffleProduct
from app.models.store import StoreProduct


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
    db: Session, user_id: int, store_product_id: int, quantity: int, points_spent: int
) -> StorageItem:
    item = StorageItem(
        user_id=user_id,
        source="store",
        store_product_id=store_product_id,
        quantity=quantity,
        points_spent=points_spent,
    )
    db.add(item)
    db.flush()
    return item


# 내 보관함 — 당첨/구매 상품 정보를 붙여서 최신순으로
def get_user_storage_items(db: Session, user_id: int) -> list[dict]:
    rows = (
        db.query(StorageItem, RaffleProduct, StoreProduct)
        .outerjoin(RaffleProduct, StorageItem.raffle_product_id == RaffleProduct.raffle_product_id)
        .outerjoin(StoreProduct, StorageItem.store_product_id == StoreProduct.store_product_id)
        .filter(StorageItem.user_id == user_id)
        .order_by(StorageItem.created_at.desc(), StorageItem.storage_item_id.desc())
        .all()
    )
    result = []
    for item, raffle, store in rows:
        product = raffle or store
        result.append({
            "storage_item_id": item.storage_item_id,
            "source": item.source,
            "raffle_product_id": item.raffle_product_id,
            "store_product_id": item.store_product_id,
            "product_name": product.product_name if product else "(삭제된 상품)",
            "image_url": product.image_url if product else None,
            "quantity": item.quantity,
            "price_krw": raffle.price_krw if raffle else None,
            "point_type": store.point_type if store else None,
            "points_spent": item.points_spent,
            "status": item.status,
            "address_id": item.address_id,
            "requested_at": item.requested_at,
            "created_at": item.created_at,
        })
    return result


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
