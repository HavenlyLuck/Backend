from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Literal

class StorageItemResponse(BaseModel):
    storage_item_id: int
    source: Literal["raffle", "store"]
    raffle_product_id: Optional[int] = None
    store_product_id: Optional[int] = None
    product_name: str
    image_url: Optional[str] = None
    quantity: int
    price_krw: Optional[int] = None                       # 당첨 상품 정가
    point_type: Optional[Literal["woon", "ssal"]] = None  # 상점 구매 포인트 종류
    points_spent: Optional[int] = None
    status: Literal["ready", "requested", "shipped"]
    address_id: Optional[int] = None
    requested_at: Optional[datetime] = None
    created_at: datetime


class ShippingRequest(BaseModel):
    storage_item_ids: list[int]
    address_id: int
