from sqlalchemy import Column, Integer, String, Text, DateTime, Enum, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


# 쿠지 1세트(한 판) — 이 안에 상위상·하위상 상품과 제비들이 들어간다
class KujiSet(Base):
    __tablename__ = "kuji_sets"
    kuji_set_id        = Column(Integer, primary_key=True, autoincrement=True)
    admin_id           = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    title              = Column(String(200), nullable=False)
    description        = Column(Text, nullable=True)
    image_url          = Column(String(500), nullable=True)   # 목록·배너용 대표 이미지 (상위상 사진과 별개)
    ticket_price       = Column(Integer, nullable=False)      # 제비 1장당 운포인트
    total_tickets      = Column(Integer, nullable=False)      # 상위상 + 하위상 개수 합 (라스트원상은 안 들어감)
    remaining_tickets  = Column(Integer, nullable=False)
    status             = Column(Enum("open", "sold_out", "closed", name="kuji_status"), nullable=False, default="open", server_default="open")
    # 라스트원상 — 마지막 제비를 뽑은 사람에게 추가로 주는 상 (제비 장수에는 안 들어가고 원가에만 들어감)
    last_one_name      = Column(String(200), nullable=True)
    last_one_image_url = Column(String(500), nullable=True)
    last_one_cost      = Column(Integer, nullable=True)
    last_one_user_id   = Column(Integer, ForeignKey("users.user_id"), nullable=True)
    board_version      = Column(Integer, nullable=False, default=1, server_default="1")  # 제비가 뽑힐 때마다 +1 — 제비판 조회에서 바뀐 게 없으면 빈 응답
    created_at         = Column(DateTime, server_default=func.now())
    updated_at         = Column(DateTime, server_default=func.now(), onupdate=func.now())

    prizes = relationship("KujiPrize", order_by="KujiPrize.sort_order", lazy="selectin")


# 쿠지 상품 — 등급(A, B, …)은 상위상부터 순서대로 매긴다
class KujiPrize(Base):
    __tablename__ = "kuji_prizes"
    kuji_prize_id      = Column(Integer, primary_key=True, autoincrement=True)
    kuji_set_id        = Column(Integer, ForeignKey("kuji_sets.kuji_set_id"), nullable=False, index=True)
    tier               = Column(Enum("upper", "lower", name="kuji_prize_tier"), nullable=False)
    grade              = Column(String(5), nullable=False)
    name               = Column(String(200), nullable=False)
    image_url          = Column(String(500), nullable=True)
    quantity           = Column(Integer, nullable=False)
    remaining_quantity = Column(Integer, nullable=False)
    cost               = Column(Integer, nullable=False, default=0, server_default="0")  # 개당 원가(원) — 관리자 전용
    sort_order         = Column(Integer, nullable=False)


# 제비 — 등록할 때 상품을 섞어서 번호마다 미리 정해 둔다
class KujiTicket(Base):
    __tablename__ = "kuji_tickets"
    __table_args__ = (UniqueConstraint("kuji_set_id", "ticket_number", name="uq_kuji_ticket_number"),)
    kuji_ticket_id     = Column(Integer, primary_key=True, autoincrement=True)
    kuji_set_id        = Column(Integer, ForeignKey("kuji_sets.kuji_set_id"), nullable=False, index=True)
    ticket_number      = Column(Integer, nullable=False)       # 제비판 번호 (1부터)
    kuji_prize_id      = Column(Integer, ForeignKey("kuji_prizes.kuji_prize_id"), nullable=False)
    drawn_by_user_id   = Column(Integer, ForeignKey("users.user_id"), nullable=True)
    drawn_at           = Column(DateTime, nullable=True)
