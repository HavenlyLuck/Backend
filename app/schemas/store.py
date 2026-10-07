from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Literal

StoreCategory = Literal["figure", "goods", "card", "coupon", "avatar"]

# 상점별로 고를 수 있는 분류
STORE_CATEGORIES: dict[str, set[str]] = {
    "woon": {"figure", "goods", "card"},
    "ssal": {"coupon", "goods", "avatar"},
}

class StoreProductResponse(BaseModel):
    store_product_id: int
    product_name: str
    description: Optional[str] = None
    point_type: Literal["woon", "ssal"]
    category: Optional[StoreCategory] = None
    price: int
    stock: int
    image_url: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class StorePurchaseRequest(BaseModel):
    quantity: int


class StorePurchaseResponse(BaseModel):
    storage_item_id: int
    store_product_id: int
    quantity: int
    points_spent: int
    point_type: Literal["woon", "ssal"]
    remaining_stock: int
