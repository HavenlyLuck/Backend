from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context

# .env에서 환경변수 읽어오기
from dotenv import load_dotenv
import os
load_dotenv()

# 모델 Base 가져오기 (나중에 모델 만들면 여기 추가)
from app.models import User
from app.database import Base

config = context.config

# DB URL을 .env에서 읽어서 alembic에 주입
DB_URL = f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
config.set_main_option("sqlalchemy.url", DB_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 여기가 핵심 — None 대신 Base.metadata로 바꿔야 autogenerate 작동
target_metadata = Base.metadata

def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()