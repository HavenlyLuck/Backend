from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, DateTime, JSON, ForeignKey
from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AlimtalkMessage(Base):
    """보낼(보낸) 카카오 알림톡 — 응모·추첨·배송 처리와 같은 트랜잭션에서 쌓고, 서버 주기 작업이 솔라피로 보낸다.
    전화번호는 저장하지 않고 보낼 때 회원 정보에서 꺼낸다 (탈퇴했으면 보내지 않는다)"""
    __tablename__ = "alimtalk_messages"
    message_id   = Column(Integer, primary_key=True, autoincrement=True)
    # 같은 알림을 두 번 쌓지 않게 — 예: raffle_entered:응모ID, raffle_sold_out:상품ID:회원ID, shipped:회원ID:첫 보관함ID
    dedup_key    = Column(String(120), unique=True, nullable=False)
    user_id      = Column(Integer, ForeignKey("users.user_id"), nullable=False, index=True)
    kind         = Column(String(20), nullable=False)    # raffle_entered / raffle_sold_out / raffle_failed / shipped
    # 알림 내용 (상품명·응모권 수 등). 템플릿 변수(#{...})로는 보낼 때 바꾼다 — app/services/alimtalk.py build_variables
    data         = Column(JSON, nullable=False)
    # pending 대기 → sending 보내는 중 → sent 접수 완료 / failed 실패 / skipped 보내지 않음(설정 없음·탈퇴·오래됨)
    status       = Column(String(10), nullable=False, default="pending", server_default="pending", index=True)
    attempts     = Column(Integer, nullable=False, default=0, server_default="0")
    solapi_message_id = Column(String(64), nullable=True)   # 솔라피가 돌려준 메시지 ID (솔라피 콘솔에서 결과 조회)
    error        = Column(String(500), nullable=True)
    created_at   = Column(DateTime, default=_utcnow, nullable=False, index=True)   # UTC
    # 발송 대기에 들어간 시각 — 처음엔 created_at과 같고, 관리자가 다시 보내기를 누르면 그때로 바뀐다 (너무 늦은 알림은 보내지 않는다)
    queued_at    = Column(DateTime, default=_utcnow, nullable=False)
    attempted_at = Column(DateTime, nullable=True)   # 마지막으로 보내기 시작한 시각
    sent_at      = Column(DateTime, nullable=True)
