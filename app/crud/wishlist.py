from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.store import StoreProduct
from app.models.wishlist import WishlistItem


class WishlistError(Exception):
    pass


# 내 찜 목록 — 최근에 찜한 순. 관리자가 삭제한 상품은 빼고 보여준다
def get_wishlist(db: Session, user_id: int) -> list[tuple[WishlistItem, StoreProduct]]:
    return (
        db.query(WishlistItem, StoreProduct)
        .join(StoreProduct, WishlistItem.store_product_id == StoreProduct.store_product_id)
        .filter(WishlistItem.user_id == user_id, StoreProduct.deleted_at.is_(None))
        .order_by(WishlistItem.created_at.desc(), WishlistItem.wishlist_item_id.desc())
        .all()
    )


# 찜하기 — 이미 찜한 상품이면 그대로 둔다
def add(db: Session, user_id: int, store_product_id: int) -> None:
    product = db.query(StoreProduct).filter(
        StoreProduct.store_product_id == store_product_id, StoreProduct.deleted_at.is_(None)
    ).first()
    if product is None:
        raise WishlistError("상품을 찾을 수 없습니다")
    if product.pay_type != "cash":
        raise WishlistError("일반 상점 상품만 찜할 수 있습니다")
    exists = db.query(WishlistItem.wishlist_item_id).filter(
        WishlistItem.user_id == user_id, WishlistItem.store_product_id == store_product_id
    ).first()
    if exists:
        return
    db.add(WishlistItem(user_id=user_id, store_product_id=store_product_id))
    try:
        db.commit()
    except IntegrityError:
        # 동시에 두 번 눌러 이미 들어간 경우
        db.rollback()


def remove(db: Session, user_id: int, store_product_id: int) -> None:
    db.query(WishlistItem).filter(
        WishlistItem.user_id == user_id, WishlistItem.store_product_id == store_product_id
    ).delete(synchronize_session=False)
    db.commit()
