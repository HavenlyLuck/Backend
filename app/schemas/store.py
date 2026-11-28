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
    funding_disabled: bool = False
    sale_mode: Literal["limited", "regular"] = "limited"   # 일반(regular)은 개수 없이 계속 판다 — stock은 0
    catalog_item_id: Optional[int] = None                  # 등록 상품 (장부용)
    created_at: datetime
    sold_count: Optional[int] = None                       # 관리자 목록에서만: 지금까지 팔린 개수 (구매 취소 제외)

    class Config:
        from_attributes = True


# 상점 상품의 응모 전환 모금 현황
#  available: 지금 응모권을 사서 모금에 참여(또는 새로 열기)할 수 있는지
#  raffle_product_id: 진행 중인 모금 (없으면 아직 아무도 시작하지 않음)
#  sold_slots / threshold / total_slots: 팔린 응모권 / 전환에 필요한 응모권(1/3) / 전체 응모권
#  ends_at: 모금 마감 (이때까지 못 모으면 전부 환불), duration_days: 새 모금의 기간
class StoreFundingStatus(BaseModel):
    available: bool
    unavailable_reason: Optional[str] = None   # available이 false인 이유 (중복 응모 · 재고 없음 등)
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
    # 쌀 응모권(쿠폰) 상품만 — 계정당 한 주에 살 수 있는 장수, 로그인했으면 이번 주에 이미 산 장수
    weekly_limit: Optional[int] = None
    bought_this_week: Optional[int] = None


class StorePurchaseRequest(BaseModel):
    quantity: int


class StorePurchaseResponse(BaseModel):
    storage_item_id: Optional[int] = None   # 쌀 응모권 상품은 보관함 상품이 아니라 쌀 응모권으로 받으므로 없다
    store_product_id: int
    quantity: int
    amount_spent: int
    pay_type: Literal["cash", "ssal"]
    remaining_stock: int
    free_tickets: int = 0   # 쌀 응모권 상품: 받은 쌀 응모권 장수
    point_used: int = 0   # 결제 상점: 할인에 쓴 쌀포인트 (카드 결제 금액 = amount_spent - point_used)


class StoreStockUpdate(BaseModel):
    stock: int
