from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Literal

class StorageItemResponse(BaseModel):
    storage_item_id: int
    source: Literal["raffle", "store", "kuji"]
    raffle_product_id: Optional[int] = None
    store_product_id: Optional[int] = None
    kuji_set_id: Optional[int] = None
    kuji_prize_id: Optional[int] = None
    product_name: str
    image_url: Optional[str] = None
    quantity: int
    price_krw: Optional[int] = None                       # 당첨 상품 정가
    pay_type: Optional[Literal["cash", "ssal"]] = None  # cash: 카드 결제(원), ssal: 쌀포인트
    amount_spent: Optional[int] = None
    status: Literal["ready", "requested", "shipped"]
    address_id: Optional[int] = None
    requested_at: Optional[datetime] = None
    created_at: datetime
    carrier: Optional[str] = None
    tracking_number: Optional[str] = None
    shipped_at: Optional[datetime] = None


class ShippingRequest(BaseModel):
    storage_item_ids: list[int]
    address_id: int


class AdminShippingAddress(BaseModel):
    recipient: str
    phone: str
    zip_code: Optional[str] = None
    address1: str
    address2: Optional[str] = None


# 관리자 배송 관리 — 보관함 상품 + 누가 · 어디로
class AdminShippingItemResponse(StorageItemResponse):
    user_id: int
    nickname: str
    address: Optional[AdminShippingAddress] = None


class AdminShipRequest(BaseModel):
    storage_item_ids: list[int]
    carrier: str
    tracking_number: str
