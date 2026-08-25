from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Literal

class PointWalletResponse(BaseModel):
    woon_point: int
    ssal_point: int

    class Config:
        from_attributes = True


class PointTransactionResponse(BaseModel):
    transaction_id: int
    point_type: Literal["woon", "ssal"]
    amount: int
    balance_after: int
    reason: Literal["raffle_entry", "store_purchase", "admin_grant", "refund"]
    reference_id: Optional[int] = None
    description: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
