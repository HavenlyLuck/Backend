from pydantic import BaseModel
from datetime import date
from typing import Optional, Literal


class SaleRecord(BaseModel):
    id: str
    date: str                    # YYYY-MM-DD (한국 시간)
    type: Literal["응모", "쿠지", "상점"]
    pay: Literal["cash", "ssal"]
    title: str
    buyer: str
    revenue: int                 # 카드 결제 금액(원). 쌀포인트 결제는 0
    ssal_price: int              # 쌀포인트로 산 경우 쓴 쌀포인트
    cost: int                    # 나간 물건의 원가 합계(원)
    item_id: Optional[int] = None


class ExpenseResponse(BaseModel):
    expense_id: int
    spent_on: date
    label: str
    amount: int

    class Config:
        from_attributes = True


class ExpenseCreate(BaseModel):
    spent_on: date
    label: str
    amount: int


# 기간 손익에 필요한 것 — 판매 기록 · 부대비용 · 입고(물건 사는 데 쓴 돈)
class FinanceResponse(BaseModel):
    sales: list[SaleRecord]
    expenses: list[ExpenseResponse]
    purchases: int
