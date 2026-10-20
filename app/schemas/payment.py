from pydantic import BaseModel
from typing import Literal, Optional

from app.schemas.raffle import RaffleEntryCreateResponse
from app.schemas.kuji import KujiDrawResponse
from app.schemas.store import StorePurchaseResponse

PaymentOrderType = Literal["raffle_entry", "kuji_draw", "store_purchase"]


# 결제 주문 만들기 — raffle_entry: quantity(응모권 장수), kuji_draw: ticket_numbers, store_purchase: quantity
class PaymentPrepareRequest(BaseModel):
    order_type: PaymentOrderType
    target_id: int                      # raffle_product_id / kuji_set_id / store_product_id
    quantity: Optional[int] = None
    ticket_numbers: Optional[list[int]] = None


# 결제창 구매자 정보 (KG이니시스 PC 결제는 이름·전화번호·이메일이 필수)
class PaymentCustomer(BaseModel):
    full_name: str
    phone_number: str
    email: str


# payment_id가 없으면 결제창을 열지 않는다 — 쿠지에서 고른 제비가 이미 나간 경우(conflict_ticket_numbers)
class PaymentPrepareResponse(BaseModel):
    payment_id: Optional[str] = None
    order_name: str = ""
    amount: int = 0
    customer: Optional[PaymentCustomer] = None
    conflict_ticket_numbers: list[int] = []


# 결제 완료 처리 결과 — paid면 주문 종류에 맞는 결과가 하나 들어 있다.
# cancelled면 지급할 수 없어서 결제를 취소한 것(message에 이유), pending이면 아직 결제가 확인되지 않은 것
class PaymentCompleteResponse(BaseModel):
    payment_id: str
    order_type: PaymentOrderType
    status: Literal["paid", "pending", "failed", "cancelled"]
    message: Optional[str] = None
    raffle_entry: Optional[RaffleEntryCreateResponse] = None
    kuji_draw: Optional[KujiDrawResponse] = None
    store_purchase: Optional[StorePurchaseResponse] = None
