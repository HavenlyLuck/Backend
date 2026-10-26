from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.sql import func
from app.database import Base

class ShippingAddress(Base):
    __tablename__ = "shipping_addresses"
    address_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id    = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    label      = Column(String(50), nullable=False)
    recipient  = Column(String(50), nullable=False)
    phone      = Column(String(20), nullable=False)
    zip_code   = Column(String(10), nullable=True)
    address1   = Column(String(255), nullable=False)
    address2   = Column(String(255), nullable=True)
    is_default = Column(Boolean, default=False, nullable=False, server_default="0")
    created_at = Column(DateTime, server_default=func.now())
    # 배송지가 5개를 넘어 정리되면 숨기기만 한다 — 이미 배송 신청된 보관함 상품이 이 배송지를 가리키고 있을 수 있다
    deleted_at = Column(DateTime, nullable=True)
