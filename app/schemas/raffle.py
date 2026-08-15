from pydantic import BaseModel, computed_field
from datetime import datetime, timezone
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
    ends_at: datetime
    drawn_at: Optional[datetime] = None

    class Config:
        from_attributes = True

    @computed_field
    @property
    def remaining_seconds(self) -> int:
        ends_at = self.ends_at.replace(tzinfo=timezone.utc) if self.ends_at.tzinfo is None else self.ends_at
        delta = ends_at - datetime.now(timezone.utc)
        return max(0, int(delta.total_seconds()))

    @computed_field
    @property
    def is_open(self) -> bool:
        return self.status == "open" and self.remaining_seconds > 0
