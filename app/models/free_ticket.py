from sqlalchemy import Column, Integer, DateTime, Enum, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


# 보관함의 쌀 응모권 1장 — 응모 상품에 결제 대신 쓸 수 있다 (낙첨돼도 쌀포인트 환급 없음)
#   first_purchase: 추천인을 등록한 사람이 첫 응모권을 샀을 때 받는 첫 구매 선물 (related_user_id = 추천해 준 사람)
#   referral      : 내가 추천한 사람이 첫 응모권을 샀을 때 받는 추천 응모권 (related_user_id = 추천받은 사람)
#   signup_event  : 오픈 이벤트 기간(SIGNUP_EVENT_END_DATE까지)에 가입하면 받는 가입 선물
#   store_purchase: 쌀포인트 상점에서 산 응모권 (계정당 한 주에 2장까지)
#   idea_contest  : 아바타 아이디어 공모전 수상 (1등 10장, 2등 7장, 3등 5장)
#   storage_convert: 보관 기한(30일) 안에 배송 신청하지 않은 응모 당첨·쿠지 상품이 바뀐 응모권
#   review_photo  : 사진 후기 보상 (보관함 상품 1건당 평생 1장 — storage_items.review_rewarded_at)
# 쓰면 raffle_entry_id · used_at이 채워지고, 그 응모가 취소되면 다시 비워져 보관함으로 돌아온다
class FreeTicket(Base):
    __tablename__ = "free_tickets"
    free_ticket_id  = Column(Integer, primary_key=True, autoincrement=True)
    user_id         = Column(Integer, ForeignKey("users.user_id"), nullable=False, index=True)
    kind            = Column(Enum("first_purchase", "referral", "signup_event", "store_purchase", "idea_contest", "storage_convert", "review_photo", name="free_ticket_kind"), nullable=False)
    related_user_id = Column(Integer, ForeignKey("users.user_id"), nullable=True)
    store_product_id = Column(Integer, ForeignKey("store_products.store_product_id"), nullable=True)   # store_purchase: 산 쿠폰 상품 (장부용)
    raffle_entry_id = Column(Integer, ForeignKey("raffle_entries.entry_id"), nullable=True, index=True)
    used_at         = Column(DateTime, nullable=True)
    created_at      = Column(DateTime, server_default=func.now())
