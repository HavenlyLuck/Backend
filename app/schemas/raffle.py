from pydantic import BaseModel, computed_field
from datetime import datetime, timezone
from typing import Optional, Literal

class RaffleProductResponse(BaseModel):
    raffle_product_id: int
    product_name: str
    description: Optional[str] = None
    price_krw: int
    ticket_price: int
    total_slots: int
    sold_slots: int = 0
    image_url: Optional[str] = None
    status: Literal["funding", "open", "completed", "cancelled"]
    starts_at: datetime
    ends_at: datetime
    sold_out_at: Optional[datetime] = None
    drawn_at: Optional[datetime] = None
    winner_entry_number: Optional[int] = None
    winner_user_id: Optional[int] = None
    draw_video_url: Optional[str] = None
    # drand 공개 난수 추첨 정보 — 라운드는 매진 순간 정해지고, 난수·서명은 추첨 뒤에 채워진다
    drand_round: Optional[int] = None
    drand_randomness: Optional[str] = None
    drand_signature: Optional[str] = None
    funding_store_product_id: Optional[int] = None   # 상점 상품에서 전환 모금으로 만들어진 응모면 그 상점 상품
    converted_at: Optional[datetime] = None          # 응모 상품으로 전환된 시각

    class Config:
        from_attributes = True

    @computed_field
    @property
    def remaining_seconds(self) -> int:
        ends_at = self.ends_at.replace(tzinfo=timezone.utc) if self.ends_at.tzinfo is None else self.ends_at
        delta = ends_at - datetime.now(timezone.utc)
        return max(0, int(delta.total_seconds()))

    @computed_field
    @property
    def is_open(self) -> bool:
        return self.status == "open" and self.remaining_seconds > 0

    @computed_field
    @property
    def remaining_slots(self) -> int:
        return max(0, self.total_slots - self.sold_slots)


class RaffleEntryResponse(BaseModel):
    entry_id: int
    raffle_product_id: int
    ticket_count: int
    amount_paid: int   # 결제 금액(원)
    created_at: datetime
    entry_number: int

    class Config:
        from_attributes = True


# 응모권 구매 직후 응답 — 이 상품에서의 내 응모 번호(최초 응모 시 한 번만 부여, 이후 재구매해도 동일)와
# 이 상품에 대한 누적 구매 수량을 함께 내려준다
class RaffleEntryCreateResponse(RaffleEntryResponse):
    total_ticket_count: int

    class Config:
        from_attributes = True


# 추첨 룰렛을 그리기 위한 참가자별 응모권 집계 (응모 번호 하나 = 구슬 개수 = ticket_count 합)
class RaffleEntrantResponse(BaseModel):
    entry_number: int
    ticket_count: int


class MyRaffleEntryResponse(BaseModel):
    entry_id: int
    raffle_product_id: int
    ticket_count: int
    amount_paid: int   # 결제 금액(원)
    entry_number: int
    created_at: datetime
    product_name: str
    image_url: Optional[str] = None
    price_krw: int
    status: Literal["funding", "open", "completed", "cancelled"]
    ends_at: datetime
    sold_out_at: Optional[datetime] = None
    winner_entry_number: Optional[int] = None
    draw_video_url: Optional[str] = None
    result_checked_at: Optional[datetime] = None   # 당첨결과를 확인한 시각 (없으면 아직 안 봄)
    funding_store_product_id: Optional[int] = None  # 응모 전환 모금 중이면 그 상점 상품 (상세는 상점 페이지에서)
    bought_in_funding: bool = False   # 전환 모금 때 산 응모권 — 응모 상품으로 전환된 뒤에는 취소할 수 없다

    class Config:
        from_attributes = True


# 번개 추첨 화면에 세울 응모자 한 명 — 응모 번호와 캐릭터 착장만 내려준다(닉네임 등 개인정보는 제외)
class RaffleCastMember(BaseModel):
    entry_number: int
    ticket_count: int
    avatar_config: Optional[dict] = None
    nickname: Optional[str] = None                # 추첨 연출 마지막에 당첨자 이름표로 띄운다


class RaffleDrawCastResponse(BaseModel):
    raffle_product_id: int
    sold_out_at: Optional[datetime] = None
    draw_at: Optional[datetime] = None            # 자동 추첨 예정 시각
    winner_entry_number: Optional[int] = None     # 추첨 전에는 None
    drand_round: Optional[int] = None             # 추첨에 쓸 drand 라운드 (매진 순간 정해짐)
    drand_randomness: Optional[str] = None        # 추첨 전에는 None
    cast: list[RaffleCastMember]


# 내 응모 취소 요청 — ticket_count가 없으면 전부 취소
class RaffleEntryCancelRequest(BaseModel):
    ticket_count: Optional[int] = None


# 내 응모 취소 결과 — refunded가 False면 카드 환불 요청이 잠시 실패해 서버가 다시 시도하는 중
class RaffleEntryCancelResponse(BaseModel):
    raffle_product_id: int
    cancelled_tickets: int
    remaining_tickets: int
    returned_free_tickets: int = 0   # 무료 응모권으로 응모한 장수 중 보관함으로 돌려준 수
    refunded: bool


# 보관함 무료 응모권으로 응모 — ticket_count장 사용
class FreeTicketEntryRequest(BaseModel):
    ticket_count: int = 1
