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
    catalog_item_id: Optional[int] = None     # 등록 상품 연결 (재고 확인·묶기 없음, 장부용)
    point_amount: Optional[int] = None        # 쌀포인트 상 — 하위상만. 뽑히면 보관함 대신 쌀포인트 적립


class KujiPrizeResponse(BaseModel):
    kuji_prize_id: int
    tier: KujiTier
    grade: str
    name: str
    image_url: Optional[str] = None
    quantity: int
    remaining_quantity: int
    point_amount: Optional[int] = None     # 쌀포인트 상이면 적립 포인트 (실물 상은 null)
    catalog_item_id: Optional[int] = None  # 등록 상품 (장부용)

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
    last_one_catalog_item_id: Optional[int] = None
    created_at: datetime
    sold_out_at: Optional[datetime] = None

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
    point_amount: Optional[int] = None     # 쌀포인트 상이면 적립된 포인트 (실물 상은 null)


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
