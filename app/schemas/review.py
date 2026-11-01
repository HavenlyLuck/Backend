from pydantic import BaseModel
from datetime import datetime
from typing import Literal, Optional

ProductType = Literal["raffle", "store", "kuji"]


class ReviewResponse(BaseModel):
    review_id: int
    rating: int
    title: str
    content: str
    image_url: Optional[str] = None
    product_name: Optional[str] = None
    product_type: Optional[ProductType] = None
    pay_type: Optional[Literal["cash", "ssal"]] = None   # 상점 상품일 때만 — cash: 일반 상점, ssal: 쌀포인트 상점
    nickname: str
    is_mine: bool = False
    created_at: datetime


# 후기를 쓸 수 있는 내 보관함 상품 (아직 후기를 안 쓴 것)
class ReviewableItem(BaseModel):
    storage_item_id: int
    product_name: str
    product_type: ProductType
    pay_type: Optional[Literal["cash", "ssal"]] = None
    image_url: Optional[str] = None
    created_at: datetime


class InquiryCreate(BaseModel):
    title: str
    content: str
    is_private: bool = False


class InquiryAnswer(BaseModel):
    answer: str


# 비공개 문의를 본인·관리자가 아닌 사람이 보면 title은 가려지고 content·answer는 None
class InquiryResponse(BaseModel):
    inquiry_id: int
    title: str
    content: Optional[str] = None
    is_private: bool
    answer: Optional[str] = None
    answered: bool
    answered_at: Optional[datetime] = None
    nickname: str
    is_mine: bool = False
    created_at: datetime
