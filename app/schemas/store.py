from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Literal

class StoreProductResponse(BaseModel):
    store_product_id: int
    product_name: str
    description: Optional[str] = None
    point_type: Literal["woon", "ssal"]
    price: int
    stock: int
    image_url: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
