# 회원 탈퇴와 법정 보존 정보 파기 (개인정보처리방침 제5조)
#
# 탈퇴하면
#   - 아이디·닉네임·이메일·휴대폰·이름·비밀번호·캐릭터는 users 행에서 지우고 가명 값으로 바꾼다
#     (결제·응모·보관함 기록이 users를 가리키고 있어 행 자체는 남긴다)
#   - 계약·결제·공급 기록이 누구 것인지 확인할 정보(아이디·이름·휴대폰·이메일)는 withdrawn_users로 따로 옮겨 5년 보관
#   - 배송에 쓴 배송지는 숨겨서 5년 보관, 쓰지 않은 배송지는 바로 지운다
#   - 문의는 분쟁 기록이라 비공개로 돌려 3년 보관, 후기(사진 파일 포함)·아바타 아이템은 바로 지운다
#   - 남은 쌀포인트·쌀 응모권(무료 응모권)과 배송 신청하지 않은 보관함 상품은 소멸 (탈퇴 화면에서 동의받음)
# 보관 기간이 지나면 purge_expired()가 지운다 (main.py 주기 작업)
import secrets
from typing import Optional
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.address import ShippingAddress
from app.models.avatar_item import UserAvatarItem
from app.models.free_ticket import FreeTicket
from app.models.inquiry import Inquiry
from app.models.payment import Payment
from app.models.point import PointWallet, PointTransaction
from app.models.privacy import WithdrawnUser
from app.models.raffle import RaffleProduct, RaffleEntry
from app.models.review import Review
from app.models.storage import StorageItem
from app.models.user import User
from app.models.wishlist import WishlistItem

# 전자상거래법 시행령 제6조 — 계약·결제·공급 기록 5년, 불만·분쟁 기록 3년
CONTRACT_RETENTION = timedelta(days=365 * 5 + 1)
DISPUTE_RETENTION = timedelta(days=365 * 3 + 1)
# 결제창을 띄운 뒤 이 시간 안의 결제 대기 주문이 있으면 아직 결제 중으로 본다 (그 뒤엔 주기 작업이 실패 처리한다)
PAYMENT_IN_PROGRESS = timedelta(hours=2)
# 발송 뒤 배송완료가 확인되지 않아도 이 기간이 지나면 배송이 끝난 것으로 본다 (배송 조회가 안 되는 택배 대비)
SHIPPING_IN_PROGRESS = timedelta(days=14)

# 탈퇴 회원에게 붙이는 가명 값의 표시 — 가입 때 아이디·닉네임에 이 글자를 못 쓰게 막는다 (routers/user.py)
WITHDRAWN_MARK = "~"


class WithdrawalError(Exception):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# 바로 탈퇴할 수 없는 이유 (없으면 None) — 프론트가 메시지를 그대로 보여준다
def blocking_reason(db: Session, user: User) -> Optional[str]:
    now = _now()
    if user.is_admin:
        return "관리자 계정은 화면에서 탈퇴할 수 없어요. 다른 관리자에게 권한 해제를 요청해 주세요."

    in_progress_raffle = (
        db.query(RaffleEntry.entry_id)
        .join(RaffleProduct, RaffleProduct.raffle_product_id == RaffleEntry.raffle_product_id)
        .filter(RaffleEntry.user_id == user.user_id, RaffleProduct.status.in_(("funding", "open")))
        .first()
    )
    if in_progress_raffle:
        return "진행 중인 응모가 있어요. 응모를 취소하거나 추첨이 끝난 뒤 탈퇴할 수 있어요."

    paying = (
        db.query(Payment.payment_id)
        .filter(
            Payment.user_id == user.user_id,
            or_(
                Payment.status == "cancel_requested",
                and_(Payment.status == "pending", Payment.created_at > now - PAYMENT_IN_PROGRESS),
            ),
        )
        .first()
    )
    if paying:
        return "결제 또는 환불이 처리 중인 주문이 있어요. 처리가 끝난 뒤(최대 2시간) 다시 시도해 주세요."

    # 배송 신청하지 않은 보관함 상품(ready)은 막지 않는다 — 소멸에 동의하고 탈퇴할 수 있다
    items = db.query(StorageItem.status, StorageItem.shipped_at, StorageItem.delivered_at).filter(
        StorageItem.user_id == user.user_id
    ).all()
    if any(status == "requested" for status, _, _ in items):
        return "배송 준비 중인 상품이 있어요. 상품을 받으신 뒤 탈퇴할 수 있어요."
    if any(
        status == "shipped" and delivered_at is None and shipped_at and shipped_at > now - SHIPPING_IN_PROGRESS
        for status, shipped_at, delivered_at in items
    ):
        return "배송 중인 상품이 있어요. 상품을 받으신 뒤 탈퇴할 수 있어요."
    return None


def withdraw(db: Session, user_id: int) -> list[str]:
    """탈퇴 처리. 바로 탈퇴할 수 없으면 WithdrawalError(이유). 커밋까지 한다
    반환: 지운 후기의 사진 주소들 — 커밋 뒤에 Cloudinary에서 지운다 (파일 삭제는 되돌릴 수 없어서 DB가 먼저)"""
    # 탈퇴 처리 중에 같은 회원의 다른 요청이 끼어들지 않게 회원 행을 잠근다
    user = db.query(User).filter(User.user_id == user_id).with_for_update().first()
    if not user or user.deleted_at is not None:
        raise WithdrawalError("이미 탈퇴한 회원입니다")
    reason = blocking_reason(db, user)
    if reason:
        raise WithdrawalError(reason)

    now = _now()
    uid = user.user_id

    # 1) 법정 보존 정보는 분리 보관
    db.add(WithdrawnUser(
        user_id=uid,
        login_id=user.login_id,
        name=user.name,
        phone=user.phone,
        email=user.email,
        withdrawn_at=now,
        purge_at=now + CONTRACT_RETENTION,
    ))

    # 2) 남은 쌀포인트·쌀 응모권 소멸
    wallet = db.query(PointWallet).filter(PointWallet.user_id == uid).with_for_update().first()
    if wallet and wallet.ssal_point:
        db.add(PointTransaction(
            user_id=uid,
            amount=-wallet.ssal_point,
            balance_after=0,
            reason="withdrawal",
            description="회원 탈퇴로 소멸",
        ))
        wallet.ssal_point = 0
    db.query(FreeTicket).filter(FreeTicket.user_id == uid, FreeTicket.used_at.is_(None)).delete(synchronize_session=False)

    # 3) 게시글 — 후기는 지우고, 문의는 분쟁 기록이라 비공개로 돌려 3년 보관
    review_images = [
        url for (url,) in db.query(Review.image_url).filter(Review.user_id == uid, Review.image_url.isnot(None))
    ]
    db.query(Review).filter(Review.user_id == uid).delete(synchronize_session=False)
    db.query(Inquiry).filter(Inquiry.user_id == uid).update({Inquiry.is_private: True}, synchronize_session=False)

    # 4) 배송지 — 배송에 쓴 것은 숨겨서 보관(공급 기록), 나머지는 바로 삭제
    used_address_ids = {
        aid for (aid,) in db.query(StorageItem.address_id)
        .filter(StorageItem.user_id == uid, StorageItem.address_id.isnot(None))
        .distinct()
    }
    for addr in db.query(ShippingAddress).filter(ShippingAddress.user_id == uid).all():
        if addr.address_id in used_address_ids:
            addr.deleted_at = addr.deleted_at or now
            addr.is_default = False
        else:
            db.delete(addr)

    # 5) 아바타 아이템
    db.query(UserAvatarItem).filter(UserAvatarItem.user_id == uid).delete(synchronize_session=False)
    db.query(WishlistItem).filter(WishlistItem.user_id == uid).delete(synchronize_session=False)

    # 6) 회원 행의 개인정보를 지우고 가명 값으로 바꾼다 (UNIQUE 컬럼은 회원번호로 겹치지 않게)
    user.login_id = f"{WITHDRAWN_MARK}withdrawn{uid}"
    user.nickname = f"탈퇴회원{WITHDRAWN_MARK}{uid}"
    user.email = f"withdrawn{uid}@withdrawn.invalid"
    user.phone = f"{WITHDRAWN_MARK}{uid}"
    user.name = None
    user.ci = None
    user.password = hash_password(secrets.token_urlsafe(32))   # 아무도 모르는 비밀번호 — 로그인 불가
    user.avatar_url = None
    user.avatar_config = None
    user.referral_code = None
    user.is_admin = False
    if user.review_marketing_agreed_at is not None:
        user.review_marketing_agreed_at = None
        user.review_marketing_withdrawn_at = now
    user.deleted_at = now

    db.commit()
    return review_images


def purge_expired(db: Session) -> None:
    """보관 기간이 지난 탈퇴 회원 정보를 파기한다 (주기 작업)"""
    now = _now()

    # 계약·결제·공급 기록 5년 — 분리 보관한 회원 정보와 배송지
    expired_ids = [
        uid for (uid,) in db.query(WithdrawnUser.user_id).filter(WithdrawnUser.purge_at <= now).limit(100)
    ]
    if expired_ids:
        db.query(ShippingAddress).filter(ShippingAddress.user_id.in_(expired_ids)).update({
            ShippingAddress.label: "파기",
            ShippingAddress.recipient: "파기",
            ShippingAddress.phone: "",
            ShippingAddress.zip_code: None,
            ShippingAddress.address1: "파기",
            ShippingAddress.address2: None,
        }, synchronize_session=False)
        db.query(WithdrawnUser).filter(WithdrawnUser.user_id.in_(expired_ids)).delete(synchronize_session=False)

    # 불만·분쟁 기록 3년 — 탈퇴 회원의 문의
    withdrawn = db.query(User.user_id).filter(User.deleted_at.isnot(None))
    db.query(Inquiry).filter(
        Inquiry.user_id.in_(withdrawn.scalar_subquery()),
        Inquiry.created_at <= now - DISPUTE_RETENTION,
    ).delete(synchronize_session=False)

    db.commit()
