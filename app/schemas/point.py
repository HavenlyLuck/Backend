from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Literal

class PointWalletResponse(BaseModel):
    ssal_point: int
    ssal_ticket: int = 0   # 보관함의 아직 안 쓴 쌀 응모권 수 (이벤트·추천인 보상, 낙첨돼도 쌀포인트 환급 없음)

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
