from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Enum
from sqlalchemy.sql import func
from app.database import Base

class PointWallet(Base):
    __tablename__ = "point_wallets"
    wallet_id  = Column(Integer, primary_key=True, autoincrement=True)
    user_id    = Column(Integer, ForeignKey("users.user_id"), unique=True, nullable=False)
    ssal_point = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


# 쌀포인트 거래 내역 (운포인트는 없어지고 쌀포인트만 남았다)
class PointTransaction(Base):
    __tablename__ = "point_transactions"
    transaction_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id        = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    amount         = Column(Integer, nullable=False)   # 지급 +, 차감 -
    balance_after  = Column(Integer, nullable=False)   # 거래 직후 잔액 스냅샷
    reason         = Column(Enum("store_purchase", "admin_grant", "raffle_consolation", "avatar_purchase", name="point_transaction_reason"), nullable=False)   # raffle_consolation: 낙첨 보상, avatar_purchase: 아바타 아이템 구매
    reference_id   = Column(Integer, nullable=True)   # 연관 엔티티 id (예: raffle_products.raffle_product_id)
    description    = Column(String(255), nullable=True)
    created_at     = Column(DateTime, server_default=func.now())
