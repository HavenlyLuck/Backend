"""무차별 대입 방어 — 로그인 시도 카운터, 관리자 2단계 인증

- auth_throttles: IP별 요청 횟수 제한, 아이디별 로그인 실패 잠금 (key는 해시라 IP·아이디 원문은 없다)
- users.totp_secret / totp_enabled_at / totp_last_step: 관리자 OTP (비밀키는 암호화해서 저장)

Revision ID: a4e8c2f6d1b9
Revises: d8b3f6a2c9e1
Create Date: 2026-11-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a4e8c2f6d1b9'
down_revision: Union[str, Sequence[str], None] = 'd8b3f6a2c9e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'auth_throttles',
        sa.Column('key', sa.String(length=80), nullable=False),
        sa.Column('count', sa.Integer(), nullable=False),
        sa.Column('window_start', sa.DateTime(), nullable=False),
        sa.Column('locked_until', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('key'),
    )
    op.create_index(op.f('ix_auth_throttles_window_start'), 'auth_throttles', ['window_start'], unique=False)

    op.add_column('users', sa.Column('totp_secret', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('totp_enabled_at', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('totp_last_step', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'totp_last_step')
    op.drop_column('users', 'totp_enabled_at')
    op.drop_column('users', 'totp_secret')
    op.drop_index(op.f('ix_auth_throttles_window_start'), table_name='auth_throttles')
    op.drop_table('auth_throttles')
