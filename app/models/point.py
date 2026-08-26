from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Enum
from sqlalchemy.sql import func
from app.database import Base

class PointWallet(Base):
    __tablename__ = "point_wallets"
    wallet_id  = Column(Integer, primary_key=True, autoincrement=True)
    user_id    = Column(Integer, ForeignKey("users.user_id"), unique=True, nullable=False)
    woon_point = Column(Integer, default=0, nullable=False)
    ssal_point = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class PointTransaction(Base):
    __tablename__ = "point_transactions"
    transaction_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id        = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    point_type     = Column(Enum("woon", "ssal", name="point_transaction_type"), nullable=False)
    amount         = Column(Integer, nullable=False)   # 지급 +, 차감 -
    balance_after  = Column(Integer, nullable=False)   # 거래 직후 잔액 스냅샷
    reason         = Column(Enum("raffle_entry", "store_purchase", "admin_grant", "refund", name="point_transaction_reason"), nullable=False)
    reference_id   = Column(Integer, nullable=True)   # 연관 엔티티 id (예: raffle_entries.entry_id)
    description    = Column(String(255), nullable=True)
    created_at     = Column(DateTime, server_default=func.now())
