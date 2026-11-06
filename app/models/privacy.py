from sqlalchemy import Column, Integer, BigInteger, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


# 탈퇴 회원의 법정 보존 정보 — users 행에서는 지우고 여기에 따로 둔다 (처리방침 제5조 "별도 DB로 분리 보관")
# 전자상거래법상 계약·결제·공급 기록(5년)이 누구의 것인지 확인할 때만 쓰고, purge_at이 지나면 행째 지운다
class WithdrawnUser(Base):
    __tablename__ = "withdrawn_users"
    user_id      = Column(Integer, ForeignKey("users.user_id"), primary_key=True)
    login_id     = Column(String(50), nullable=False)
    name         = Column(String(50), nullable=True)
    phone        = Column(String(20), nullable=False)
    email        = Column(String(100), nullable=False)
    withdrawn_at = Column(DateTime, nullable=False)
    purge_at     = Column(DateTime, nullable=False, index=True)   # 탈퇴 + 5년


# 관리자 접속기록 — 관리자 API 호출마다 남기고 최소 2년 보관한다 (처리방침 제9조, 안전성 확보조치 기준)
# 지우거나 고치는 API는 두지 않는다 (위변조 방지)
class AdminAccessLog(Base):
    __tablename__ = "admin_access_logs"
    log_id      = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    admin_id    = Column(Integer, nullable=False, index=True)   # 관리자 계정이 탈퇴해도 기록은 남도록 FK를 걸지 않는다
    accessed_at = Column(DateTime, nullable=False, server_default=func.now(), index=True)
    ip          = Column(String(45), nullable=True)
    method      = Column(String(10), nullable=False)
    action      = Column(String(10), nullable=False)        # 조회 / 수정 / 등록 / 삭제
    path        = Column(String(500), nullable=False)       # 대상 (경로 + 쿼리)
    user_agent  = Column(String(300), nullable=True)
