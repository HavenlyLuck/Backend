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
