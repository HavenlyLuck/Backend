from sqlalchemy import Column, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from app.database import Base


# 찜한 상품 — 일반(결제) 상점 상품만 찜할 수 있다. 회원당 같은 상품은 한 번만
class WishlistItem(Base):
    __tablename__ = "wishlist_items"
    __table_args__ = (UniqueConstraint("user_id", "store_product_id", name="uq_wishlist_user_product"),)
    wishlist_item_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id          = Column(Integer, ForeignKey("users.user_id"), nullable=False, index=True)
    store_product_id = Column(Integer, ForeignKey("store_products.store_product_id"), nullable=False)
    created_at       = Column(DateTime, server_default=func.now())
