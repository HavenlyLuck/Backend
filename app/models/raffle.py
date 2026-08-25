from sqlalchemy import Column, Integer, String, Text, DateTime, Enum, ForeignKey
from sqlalchemy.sql import func
from app.database import Base

class RaffleProduct(Base):
    __tablename__ = "raffle_products"
    raffle_product_id = Column(Integer, primary_key=True, autoincrement=True)
    admin_id           = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    product_name        = Column(String(200), nullable=False)
    description          = Column(Text, nullable=True)
    price_krw            = Column(Integer, nullable=False)
    ticket_price         = Column(Integer, nullable=False)   # 응모권 1장당 운포인트
    total_slots           = Column(Integer, nullable=False)
    image_url             = Column(String(500), nullable=True)
    status                = Column(Enum("open", "completed", "cancelled", name="raffle_status"), nullable=False, default="open", server_default="open")
    starts_at             = Column(DateTime, nullable=False)
    ends_at                = Column(DateTime, nullable=False)   # starts_at + 24시간
    drawn_at              = Column(DateTime, nullable=True)
    created_at            = Column(DateTime, server_default=func.now())
    updated_at            = Column(DateTime, server_default=func.now(), onupdate=func.now())


class RaffleEntry(Base):
    __tablename__ = "raffle_entries"
    entry_id           = Column(Integer, primary_key=True, autoincrement=True)
    raffle_product_id  = Column(Integer, ForeignKey("raffle_products.raffle_product_id"), nullable=False)
    user_id             = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    ticket_count         = Column(Integer, nullable=False)     # 이번 응모에서 구매한 응모권 수
    points_spent          = Column(Integer, nullable=False)     # ticket_count * ticket_price 스냅샷
    created_at             = Column(DateTime, server_default=func.now())
