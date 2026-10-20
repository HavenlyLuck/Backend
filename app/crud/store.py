from sqlalchemy.orm import Session
from typing import Optional

from app.models.store import StoreProduct
from app.crud import storage as storage_crud


def create_store_product(
    db: Session,
    admin_id: int,
    product_name: str,
    description: Optional[str],
    pay_type: str,
    category: str,
    price: int,
    stock: int,
    image_url: Optional[str],
) -> StoreProduct:
    product = StoreProduct(
        admin_id=admin_id,
        product_name=product_name,
        description=description,
        pay_type=pay_type,
        category=category,
        price=price,
        stock=stock,
        image_url=image_url,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def get_store_products(db: Session, pay_type: Optional[str] = None) -> list[StoreProduct]:
    query = db.query(StoreProduct)
    if pay_type:
        query = query.filter(StoreProduct.pay_type == pay_type)
    return query.order_by(StoreProduct.created_at.desc()).all()


def get_store_product(db: Session, store_product_id: int) -> Optional[StoreProduct]:
    return db.query(StoreProduct).filter(StoreProduct.store_product_id == store_product_id).first()


# 재고 차감 시 동시 구매로 재고가 음수가 되지 않도록 행 잠금으로 조회
def get_store_product_for_update(db: Session, store_product_id: int) -> Optional[StoreProduct]:
    return (
        db.query(StoreProduct)
        .filter(StoreProduct.store_product_id == store_product_id)
        .with_for_update()
        .first()
    )


class StorePurchaseError(Exception):
    pass


# 상점 구매 — 재고 차감과 보관함 적재 (commit은 호출한 쪽에서). 재고 부족이면 StorePurchaseError
def fulfill_store_purchase(
    db: Session, store_product_id: int, user_id: int, quantity: int, pay_type: str, payment_id: Optional[str] = None,
):
    if quantity <= 0:
        raise StorePurchaseError("구매 수량은 1개 이상이어야 합니다")
    product = get_store_product_for_update(db, store_product_id)
    if not product:
        raise StorePurchaseError("상품을 찾을 수 없습니다")
    if product.pay_type != pay_type:
        raise StorePurchaseError("결제 방식이 맞지 않는 상품입니다")
    if product.stock < quantity:
        raise StorePurchaseError("재고가 부족합니다")

    product.stock -= quantity
    item = storage_crud.add_store_purchase(
        db,
        user_id=user_id,
        store_product_id=product.store_product_id,
        quantity=quantity,
        amount_spent=product.price * quantity,
        payment_id=payment_id,
    )
    return product, item
