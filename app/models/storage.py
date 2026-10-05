from sqlalchemy import Column, Integer, DateTime, Enum, ForeignKey
from sqlalchemy.sql import func
from app.database import Base

class StorageItem(Base):
    __tablename__ = "storage_items"
    storage_item_id   = Column(Integer, primary_key=True, autoincrement=True)
    user_id           = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    source            = Column(Enum("raffle", "store", name="storage_source"), nullable=False)
    raffle_product_id = Column(Integer, ForeignKey("raffle_products.raffle_product_id"), unique=True, nullable=True)   # 당첨 상품 (상품당 1건)
    store_product_id  = Column(Integer, ForeignKey("store_products.store_product_id"), nullable=True)                 # 상점 구매 상품
    quantity          = Column(Integer, nullable=False, default=1, server_default="1")
    points_spent      = Column(Integer, nullable=True)     # 상점 구매 시 차감된 포인트 스냅샷
    status            = Column(Enum("ready", "requested", "shipped", name="storage_status"), nullable=False, default="ready", server_default="ready")
    address_id        = Column(Integer, ForeignKey("shipping_addresses.address_id"), nullable=True)   # 배송 신청 시 선택한 배송지
    requested_at      = Column(DateTime, nullable=True)
    created_at        = Column(DateTime, server_default=func.now())
    updated_at        = Column(DateTime, server_default=func.now(), onupdate=func.now())
