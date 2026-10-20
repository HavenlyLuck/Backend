from sqlalchemy import Column, Integer, String, Text, DateTime, Enum, ForeignKey
from sqlalchemy.sql import func
from app.database import Base

class StoreProduct(Base):
    __tablename__ = "store_products"
    store_product_id = Column(Integer, primary_key=True, autoincrement=True)
    admin_id          = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    product_name      = Column(String(200), nullable=False)
    description       = Column(Text, nullable=True)
    pay_type          = Column(Enum("cash", "ssal", name="store_pay_type"), nullable=False)   # cash: 카드 결제(원), ssal: 쌀포인트
    # 상점 세부 탭 분류 — 결제 상점: figure/goods/card, 쌀포인트 상점: coupon/goods/avatar
    category          = Column(Enum("figure", "goods", "card", "coupon", "avatar", name="store_category"), nullable=True)
    price             = Column(Integer, nullable=False)
    stock             = Column(Integer, nullable=False)
    image_url         = Column(String(500), nullable=True)
    created_at        = Column(DateTime, server_default=func.now())
    updated_at        = Column(DateTime, server_default=func.now(), onupdate=func.now())
    