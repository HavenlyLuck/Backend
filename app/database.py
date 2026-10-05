from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

DATABASE_URL = f"mysql+pymysql://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"

# READ COMMITTED: 행 잠금을 얻은 뒤의 조회가 다른 요청이 방금 커밋한 데이터를 보도록 한다.
# (기본값 REPEATABLE READ에선 잠금 전에 찍힌 스냅샷을 읽어 응모 번호 중복·초과 판매가 생겼음)
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=280,
    isolation_level="READ COMMITTED",
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 라우터에서 DB 세션 받아쓰는 의존성 함수
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()