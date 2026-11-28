from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel

from app.schemas.finance import ExpenseResponse


# 쿠지 결제 1건으로 나간 상 — 라스트원은 grade "라스트원". 쌀포인트 상은 point_amount(1개당 적립 쌀포인트)
class LedgerKujiPrize(BaseModel):
    grade: str
    name: str
    quantity: int
    point_amount: Optional[int] = None


# 판매 한 줄 — 개인정보 없이 user_id만
class LedgerSale(BaseModel):
    id: str
    at: datetime                     # UTC
    kind: Literal["raffle", "kuji", "store_cash", "store_ssal", "shipping_fee"]
    round_id: Optional[str] = None   # raffle-12 · kuji-3 · store-5 (배송비는 없음)
    title: str
    user_id: int
    pay: Literal["cash", "ssal", "ssal_ticket"]
    tickets: int                     # 응모권 · 제비 장수 / 상점 구매 수량 / 배송비: 상품 수
    amount_krw: int                  # 카드 결제 금액(원)
    amount_ssal: int                 # 쓴 쌀포인트 (쌀포인트 상점 · 카드 상점 할인)
    status: Literal["pending", "confirmed", "refunded"]
    prizes: Optional[list[LedgerKujiPrize]] = None   # kind=kuji만: 이 결제로 나간 상 (환불된 결제는 빈 목록)


# 물건이 나간 기록 — 반품은 quantity 음수
class LedgerOutflow(BaseModel):
    at: datetime
    round_id: Optional[str] = None
    catalog_item_id: Optional[int] = None
    item_name: str
    quantity: int
    reason: Literal["raffle_win", "kuji_prize", "kuji_last_one", "store_sale", "ssal_shop", "storage_convert", "return"]


class LedgerRoundItem(BaseModel):
    grade: Optional[str] = None
    catalog_item_id: Optional[int] = None
    name: str
    quantity: Optional[int] = None   # 일반 상점 상품은 개수가 없어 null


class LedgerRound(BaseModel):
    round_id: str
    kind: Literal["raffle", "kuji", "store_cash", "store_ssal"]
    title: str
    status: str
    price: int                       # 장당 가격 (상점은 1개 가격)
    tickets_total: Optional[int] = None
    tickets_sold: int
    tickets_ssal: int                # 쌀 응모권으로 응모한 장수
    created_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    items: list[LedgerRoundItem]


class LedgerPurchase(BaseModel):
    receipt_id: int
    item_id: int
    received_at: date
    supplier: Optional[str] = None
    quantity: int
    unit_cost: int
    memo: Optional[str] = None
    tax_free: bool


class LedgerCatalogItem(BaseModel):
    item_id: int
    name: str


class LedgerResponse(BaseModel):
    sales: list[LedgerSale]
    outflows: list[LedgerOutflow]
    rounds: list[LedgerRound]
    purchases: list[LedgerPurchase]
    expenses: list[ExpenseResponse]
    catalog: list[LedgerCatalogItem]
