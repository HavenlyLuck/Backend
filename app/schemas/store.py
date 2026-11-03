from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Literal

StoreCategory = Literal["figure", "goods", "card", "coupon", "avatar"]

# 상점별로 고를 수 있는 분류 — cash: 카드 결제 상점, ssal: 쌀포인트 상점
STORE_CATEGORIES: dict[str, set[str]] = {
    "cash": {"figure", "goods", "card"},
    "ssal": {"coupon", "goods", "avatar"},
}

class StoreProductResponse(BaseModel):
    store_product_id: int
    product_name: str
    description: Optional[str] = None
    pay_type: Literal["cash", "ssal"]
    category: Optional[StoreCategory] = None
    price: int
    stock: int
    image_url: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# 상점 상품의 응모 전환 모금 현황
#  available: 지금 응모권을 사서 모금에 참여(또는 새로 열기)할 수 있는지
#  raffle_product_id: 진행 중인 모금 (없으면 아직 아무도 시작하지 않음)
#  sold_slots / threshold / total_slots: 팔린 응모권 / 전환에 필요한 응모권(1/3) / 전체 응모권
#  ends_at: 모금 마감 (이때까지 못 모으면 전부 환불), duration_days: 새 모금의 기간
class StoreFundingStatus(BaseModel):
    available: bool
    raffle_product_id: Optional[int] = None
    sold_slots: int
    threshold: int
    total_slots: int
    ticket_price: int
    ends_at: Optional[datetime] = None
    duration_days: int
    banned_until: Optional[datetime] = None   # 로그인한 사람이 전환 응모권을 살 수 없는 기한 (전환 후 모금 응모권 취소 제재)


class StoreProductDetailResponse(StoreProductResponse):
    funding: Optional[StoreFundingStatus] = None   # 결제 상점 상품만 (쌀포인트 상점은 없음)


class StorePurchaseRequest(BaseModel):
    quantity: int


class StorePurchaseResponse(BaseModel):
    storage_item_id: int
    store_product_id: int
    quantity: int
    amount_spent: int
    pay_type: Literal["cash", "ssal"]
    remaining_stock: int


class StoreStockUpdate(BaseModel):
    stock: int
