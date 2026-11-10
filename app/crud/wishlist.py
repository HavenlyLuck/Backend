from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.raffle import RaffleProduct
from app.models.store import StoreProduct
from app.models.wishlist import WishlistItem


class WishlistError(Exception):
    pass


def _insert(db: Session, item: WishlistItem) -> None:
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        # 동시에 두 번 눌러 이미 들어간 경우
        db.rollback()


# ── 상점 상품 ──

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
    if not exists:
        _insert(db, WishlistItem(user_id=user_id, store_product_id=store_product_id))


def remove(db: Session, user_id: int, store_product_id: int) -> None:
    db.query(WishlistItem).filter(
        WishlistItem.user_id == user_id, WishlistItem.store_product_id == store_product_id
    ).delete(synchronize_session=False)
    db.commit()


# ── 응모 상품 ──

# 찜한 응모 상품 — 최근에 찜한 순. 전환 모금 중인 응모(상점 페이지에서 보는 것)와
# 상점에서 전환됐다가 취소돼 상점으로 돌아간 응모는 뺀다 (취소될 때 찜도 지워지지만, 그 전에 남은 기록까지 거른다)
def get_raffle_wishlist(db: Session, user_id: int) -> list[tuple[WishlistItem, RaffleProduct]]:
    returned_to_store = (RaffleProduct.status == "cancelled") & RaffleProduct.funding_store_product_id.isnot(None)
    return (
        db.query(WishlistItem, RaffleProduct)
        .join(RaffleProduct, WishlistItem.raffle_product_id == RaffleProduct.raffle_product_id)
        .filter(WishlistItem.user_id == user_id, RaffleProduct.status != "funding", ~returned_to_store)
        .order_by(WishlistItem.created_at.desc(), WishlistItem.wishlist_item_id.desc())
        .all()
    )


def add_raffle(db: Session, user_id: int, raffle_product_id: int) -> None:
    product = db.query(RaffleProduct).filter(RaffleProduct.raffle_product_id == raffle_product_id).first()
    if product is None or product.status == "funding" or (
        product.status == "cancelled" and product.funding_store_product_id is not None
    ):
        raise WishlistError("응모 상품을 찾을 수 없습니다")
    exists = db.query(WishlistItem.wishlist_item_id).filter(
        WishlistItem.user_id == user_id, WishlistItem.raffle_product_id == raffle_product_id
    ).first()
    if not exists:
        _insert(db, WishlistItem(user_id=user_id, raffle_product_id=raffle_product_id))


def remove_raffle(db: Session, user_id: int, raffle_product_id: int) -> None:
    db.query(WishlistItem).filter(
        WishlistItem.user_id == user_id, WishlistItem.raffle_product_id == raffle_product_id
    ).delete(synchronize_session=False)
    db.commit()
