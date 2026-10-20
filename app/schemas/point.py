from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Literal

class PointWalletResponse(BaseModel):
    ssal_point: int

    class Config:
        from_attributes = True


class PointTransactionResponse(BaseModel):
    transaction_id: int
    amount: int
    balance_after: int
    reason: Literal["store_purchase", "admin_grant", "raffle_consolation", "avatar_purchase"]
    reference_id: Optional[int] = None
    description: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
