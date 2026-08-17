from sqlalchemy import Column, Integer, String, Text, DateTime, Enum, ForeignKey
from sqlalchemy.sql import func
from app.database import Base

class StoreProduct(Base):
    __tablename__ = "store_products"
    store_product_id = Column(Integer, primary_key=True, autoincrement=True)
    admin_id          = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    product_name      = Column(String(200), nullable=False)
    description       = Column(Text, nullable=True)
    point_type        = Column(Enum("woon", "ssal", name="store_point_type"), nullable=False)
    price             = Column(Integer, nullable=False)
    stock             = Column(Integer, nullable=False)
    image_url         = Column(String(500), nullable=True)
    created_at        = Column(DateTime, server_default=func.now())
    updated_at        = Column(DateTime, server_default=func.now(), onupdate=func.now())
