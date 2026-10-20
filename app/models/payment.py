from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey, JSON
from sqlalchemy.sql import func
from app.database import Base


# 포트원 카드 결제 1건 — 응모권·쿠지·결제 상점 구매가 모두 이 주문을 거친다.
# pending(결제 대기) → paid(지급 완료) / cancel_requested(지급 실패·응모 취소로 환불 대기) → cancelled(환불 완료) / failed(결제 안 됨)
class Payment(Base):
    __tablename__ = "payments"
    payment_id     = Column(String(64), primary_key=True)    # 포트원 paymentId (서버가 만든다)
    user_id        = Column(Integer, ForeignKey("users.user_id"), nullable=False, index=True)
    order_type     = Column(Enum("raffle_entry", "kuji_draw", "store_purchase", name="payment_order_type"), nullable=False)
    target_id      = Column(Integer, nullable=False)          # raffle_product_id / kuji_set_id / store_product_id
    quantity       = Column(Integer, nullable=False)          # 응모권 장수 / 제비 장수 / 구매 수량
    ticket_numbers = Column(JSON, nullable=True)              # 쿠지: 고른 제비 번호들
    order_name     = Column(String(200), nullable=False)
    amount         = Column(Integer, nullable=False)          # 결제해야 하는 금액(원) — 포트원 결제 금액과 반드시 같아야 지급한다
    status         = Column(Enum("pending", "paid", "cancel_requested", "cancelled", "failed", name="payment_status"), nullable=False, default="pending", server_default="pending", index=True)
    cancel_reason  = Column(String(200), nullable=True)
    paid_at        = Column(DateTime, nullable=True)
    cancelled_at   = Column(DateTime, nullable=True)
    created_at     = Column(DateTime, server_default=func.now())
    updated_at     = Column(DateTime, server_default=func.now(), onupdate=func.now())
