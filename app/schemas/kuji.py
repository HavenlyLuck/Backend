from pydantic import BaseModel, computed_field
from datetime import datetime
from typing import Optional, Literal

KujiTier = Literal["upper", "lower"]


# 등록 요청의 상품 한 줄 — 사진은 prize_images 중 image_index번째 파일
class KujiPrizeCreate(BaseModel):
    tier: KujiTier
    name: str
    quantity: int
    cost: int = 0
    image_index: Optional[int] = None
    inventory_item_id: Optional[int] = None   # 재고에서 고른 품목


class KujiPrizeResponse(BaseModel):
    kuji_prize_id: int
    tier: KujiTier
    grade: str
    name: str
    image_url: Optional[str] = None
    quantity: int
    remaining_quantity: int

    class Config:
        from_attributes = True


class KujiPrizeAdminResponse(KujiPrizeResponse):
    cost: int


class KujiSetResponse(BaseModel):
    kuji_set_id: int
    title: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    ticket_price: int
    total_tickets: int
    remaining_tickets: int
    status: Literal["open", "sold_out", "closed"]
    prizes: list[KujiPrizeResponse]
    last_one_name: Optional[str] = None
    last_one_image_url: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# 관리자 화면용 — 원가와 예상 마진까지 내려준다
class KujiSetAdminResponse(KujiSetResponse):
    prizes: list[KujiPrizeAdminResponse]
    last_one_cost: Optional[int] = None

    @computed_field
    @property
    def total_cost(self) -> int:
        return sum(p.cost * p.quantity for p in self.prizes) + (self.last_one_cost or 0)

    @computed_field
    @property
    def expected_revenue(self) -> int:
        return self.ticket_price * self.total_tickets


# 제비판 — 뽑힌 제비만 번호와 등급을 알려준다 (안 뽑힌 제비의 상품은 절대 내려주지 않음)
class KujiDrawnTicket(BaseModel):
    ticket_number: int
    grade: str


class KujiBoardResponse(BaseModel):
    kuji_set_id: int
    version: int
    total_tickets: int
    remaining_tickets: int
    drawn: list[KujiDrawnTicket]


class KujiDrawnPrize(BaseModel):
    ticket_number: int
    kuji_prize_id: int
    grade: str
    tier: KujiTier
    name: str
    image_url: Optional[str] = None


class KujiLastOnePrize(BaseModel):
    name: str
    image_url: Optional[str] = None


# 뽑기 결과 — ok=False면 고른 제비 중 이미 나간 게 있어서 아무것도 뽑지 않았다 (부분 뽑기 없음, 결제는 자동 취소)
class KujiDrawResponse(BaseModel):
    ok: bool
    drawn: list[KujiDrawnPrize] = []
    last_one: Optional[KujiLastOnePrize] = None
    amount_paid: int = 0   # 결제 금액(원)
    conflict_ticket_numbers: list[int] = []
    board: KujiBoardResponse
