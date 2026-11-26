from pydantic import BaseModel
from datetime import datetime
from typing import Literal, Optional


class ReferralSummaryResponse(BaseModel):
    referral_code: str                          # 내 추천인 코드
    referred_by_nickname: Optional[str] = None  # 내가 등록한 추천인
    can_register: bool                          # 지금 추천인을 등록할 수 있는지 (추천인 없음 + 응모권 구매 전)
    invited_count: int                          # 내 코드로 등록한 사람 수
    rewarded_count: int                         # 그중 첫 구매까지 해서 받은 추천 응모권 수


class ReferralRegisterRequest(BaseModel):
    referral_code: str


# 보관함의 무료 응모권 — first_purchase: 첫 구매 선물(related = 나를 추천한 사람), referral: 추천 응모권(related = 내가 추천한 사람),
# signup_event: 오픈 이벤트 가입 선물, store_purchase: 쌀포인트 상점에서 산 응모권,
# idea_contest: 아바타 아이디어 공모전 수상, storage_convert: 보관 기한 전환, review_photo: 사진 후기 보상
class FreeTicketResponse(BaseModel):
    free_ticket_id: int
    kind: Literal["first_purchase", "referral", "signup_event", "store_purchase", "idea_contest", "storage_convert", "review_photo"]
    related_nickname: Optional[str] = None
    created_at: datetime
