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
