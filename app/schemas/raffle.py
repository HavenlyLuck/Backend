from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Literal

class RaffleProductResponse(BaseModel):
    raffle_product_id: int
    product_name: str
    description: Optional[str] = None
    price_krw: int
    ticket_price: int
    total_slots: int
    image_url: Optional[str] = None
    status: Literal["open", "completed", "cancelled"]
    starts_at: datetime
    drawn_at: Optional[datetime] = None

    class Config:
        from_attributes = True
