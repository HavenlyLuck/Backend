from sqlalchemy import Column, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from app.database import Base


# 찜한 상품 — 한 행에 일반(결제) 상점 상품 또는 응모 상품 하나. 회원당 같은 상품은 한 번만
class WishlistItem(Base):
    __tablename__ = "wishlist_items"
    __table_args__ = (
        UniqueConstraint("user_id", "store_product_id", name="uq_wishlist_user_product"),
        UniqueConstraint("user_id", "raffle_product_id", name="uq_wishlist_user_raffle"),
    )
    wishlist_item_id  = Column(Integer, primary_key=True, autoincrement=True)
    user_id           = Column(Integer, ForeignKey("users.user_id"), nullable=False, index=True)
    store_product_id  = Column(Integer, ForeignKey("store_products.store_product_id"), nullable=True)
    raffle_product_id = Column(Integer, ForeignKey("raffle_products.raffle_product_id"), nullable=True)
    created_at        = Column(DateTime, server_default=func.now())
