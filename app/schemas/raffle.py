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
    status: Literal["open", "completed", "cancelled"]
    starts_at: datetime
    ends_at: datetime
    sold_out_at: Optional[datetime] = None
    drawn_at: Optional[datetime] = None
    winner_entry_number: Optional[int] = None
    winner_user_id: Optional[int] = None
    draw_video_url: Optional[str] = None

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


class RaffleEntryCreate(BaseModel):
    ticket_count: int


class RaffleEntryResponse(BaseModel):
    entry_id: int
    raffle_product_id: int
    ticket_count: int
    points_spent: int
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
    points_spent: int
    entry_number: int
    created_at: datetime
    product_name: str
    image_url: Optional[str] = None
    price_krw: int
    status: Literal["open", "completed", "cancelled"]
    ends_at: datetime
    sold_out_at: Optional[datetime] = None
    winner_entry_number: Optional[int] = None
    draw_video_url: Optional[str] = None

    class Config:
        from_attributes = True


# 번개 추첨 화면에 세울 응모자 한 명 — 응모 번호와 캐릭터 착장만 내려준다(닉네임 등 개인정보는 제외)
class RaffleCastMember(BaseModel):
    entry_number: int
    ticket_count: int
    avatar_config: Optional[dict] = None


class RaffleDrawCastResponse(BaseModel):
    raffle_product_id: int
    sold_out_at: Optional[datetime] = None
    draw_at: Optional[datetime] = None            # 자동 추첨 예정 시각
    winner_entry_number: Optional[int] = None     # 추첨 전에는 None
    cast: list[RaffleCastMember]
