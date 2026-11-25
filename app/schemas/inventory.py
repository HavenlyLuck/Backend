from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional, Literal


class InventoryReceiptResponse(BaseModel):
    receipt_id: int
    item_id: int
    quantity: int
    unit_cost: int
    received_at: date
    supplier: Optional[str] = None
    memo: Optional[str] = None
    tax_free: bool = False      # 면세 입고
    created_at: datetime

    class Config:
        from_attributes = True


class InventoryAllocationResponse(BaseModel):
    product_type: Literal["raffle", "kuji", "store"]
    product_id: int
    product_name: str
    reserved: int
    sold: int


class InventoryItemResponse(BaseModel):
    item_id: int
    name: str
    image_url: Optional[str] = None
    memo: Optional[str] = None
    description: Optional[str] = None
    total_received: int
    reserved: int
    sold: int
    available: int
    avg_unit_cost: int
    last_received_at: Optional[date] = None


class InventoryItemDetailResponse(InventoryItemResponse):
    receipts: list[InventoryReceiptResponse]
    allocations: list[InventoryAllocationResponse]


class InventoryReceiptUpdate(BaseModel):
    quantity: Optional[int] = None
    unit_cost: Optional[int] = None
    received_at: Optional[date] = None
    supplier: Optional[str] = None
    memo: Optional[str] = None
    tax_free: Optional[bool] = None


# 품목 이름 · 설명(상품 설명 · 상품정보제공고시) 고치기 — 보낸 칸만 바꾼다
class InventoryItemUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
