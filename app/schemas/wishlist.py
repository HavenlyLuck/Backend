from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel


# 찜한 상품 한 개 — 상품 카드를 그릴 정보와 찜한 시각
class WishlistItemResponse(BaseModel):
    store_product_id: int
    product_name: str
    image_url: Optional[str] = None
    pay_type: Literal["cash", "ssal"]
    price: int
    stock: int
    wished_at: Optional[datetime] = None
