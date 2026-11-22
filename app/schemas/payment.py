from pydantic import BaseModel
from datetime import datetime
from typing import Literal, Optional

from app.schemas.raffle import RaffleEntryCreateResponse
from app.schemas.kuji import KujiDrawResponse
from app.schemas.store import StorePurchaseResponse
from app.schemas.storage import StorageItemResponse

# store_funding: 상점 상품의 응모 전환 모금 응모권 (target_id = 상점 상품 id)
# shipping_fee: 보관함 상품 배송 신청 배송비 (target_id = 배송지 address_id)
PaymentOrderType = Literal["raffle_entry", "kuji_draw", "store_purchase", "store_funding", "shipping_fee"]


# 결제 주문 만들기 — raffle_entry: quantity(응모권 장수), kuji_draw: ticket_numbers, store_purchase: quantity,
# shipping_fee: storage_item_ids(배송 신청할 보관함 상품) + target_id(배송지)
class PaymentPrepareRequest(BaseModel):
    order_type: PaymentOrderType
    target_id: int                      # raffle_product_id / kuji_set_id / store_product_id / address_id
    quantity: Optional[int] = None
    ticket_numbers: Optional[list[int]] = None
    storage_item_ids: Optional[list[int]] = None
    point_use: int = 0                  # store_purchase: 할인에 쓸 쌀포인트 (구매 금액의 10%까지, 1P = 1원)


# 결제창 구매자 정보 (이름·전화번호·이메일)
class PaymentCustomer(BaseModel):
    full_name: str
    phone_number: str
    email: str


# payment_id가 없으면 결제창을 열지 않는다 — 쿠지에서 고른 제비가 이미 나간 경우(conflict_ticket_numbers)
class PaymentPrepareResponse(BaseModel):
    payment_id: Optional[str] = None
    order_name: str = ""
    amount: int = 0                     # 카드로 낼 금액 (쌀포인트 할인 뒤)
    point_used: int = 0                 # 할인에 쓸 쌀포인트 — 결제가 확인되면 차감한다
    customer: Optional[PaymentCustomer] = None
    conflict_ticket_numbers: list[int] = []


# 결제 완료 처리 결과 — paid면 주문 종류에 맞는 결과가 하나 들어 있다.
# cancelled면 지급할 수 없어서 결제를 취소한 것(message에 이유), pending이면 아직 결제가 확인되지 않은 것
class PaymentCompleteResponse(BaseModel):
    payment_id: str
    order_type: PaymentOrderType
    status: Literal["paid", "pending", "failed", "cancelled"]
    message: Optional[str] = None
    # 메타 픽셀 Purchase용 (브라우저) — 실제 카드 결제 금액, 상품, 수량
    amount: int = 0
    target_id: int = 0
    quantity: int = 0
    raffle_entry: Optional[RaffleEntryCreateResponse] = None
    kuji_draw: Optional[KujiDrawResponse] = None
    store_purchase: Optional[StorePurchaseResponse] = None
    shipping: Optional[list[StorageItemResponse]] = None   # 배송비: 배송 신청된 보관함 상품들


# 마이페이지 구매 내역 1건 — 카드 결제 1건(응모권 · 쿠지 · 결제 상점 · 배송비)
# status: paid(결제 완료) / refunded(환불됨 — 응모 취소·구매 취소·지급 실패 등. 환불 처리 중이어도 refunded)
class MyPaymentResponse(BaseModel):
    payment_id: str
    order_type: PaymentOrderType
    target_id: int
    product_name: str
    image_url: Optional[str] = None
    quantity: int                       # 응모권 장수 / 제비 장수 / 구매 수량 / 배송 상품 수 (부분 취소 후엔 남은 수)
    amount: int                         # 결제 금액(원, 부분 취소 후엔 남은 금액)
    point_used: int = 0                 # 결제 상점: 할인에 쓴 쌀포인트
    status: Literal["paid", "refunded"]
    paid_at: datetime
