from sqlalchemy import Column, Integer, String, DateTime
from app.database import Base


# 무차별 대입 방어용 카운터 — IP별 요청 횟수 제한, 아이디별 로그인 실패 잠금 (app/core/throttle.py)
# 서버 프로세스·인스턴스가 여러 개여도 같은 값을 보도록 DB에 센다.
# key는 "종류:해시" 형태라 IP·아이디 원문은 남지 않는다
class AuthThrottle(Base):
    __tablename__ = "auth_throttles"
    key          = Column(String(80), primary_key=True)
    count        = Column(Integer, nullable=False, default=0)
    window_start = Column(DateTime, nullable=False, index=True)   # 이 시각부터 센 횟수
    locked_until = Column(DateTime, nullable=True)                # 로그인 실패 잠금이 풀리는 시각
