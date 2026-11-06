"""가입 동의 기록, 회원 탈퇴, 관리자 접속기록

- users: 이용약관·만 14세 확인·후기 홍보 동의(철회) 시각, 탈퇴 시각
- withdrawn_users: 탈퇴 회원의 법정 보존 정보 (분리 보관, 5년 뒤 파기)
- admin_access_logs: 관리자 API 접속기록 (최소 2년 보관)
- point_transactions.reason: 탈퇴로 소멸한 쌀포인트(withdrawal)

Revision ID: f2c8e4a6b1d9
Revises: c9e4a1f7d2b8
Create Date: 2026-11-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f2c8e4a6b1d9'
down_revision: Union[str, Sequence[str], None] = 'c9e4a1f7d2b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


OLD_REASONS = ("store_purchase", "admin_grant", "raffle_consolation", "avatar_purchase")
NEW_REASONS = OLD_REASONS + ("withdrawal",)


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('terms_agreed_at', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('age_14_confirmed_at', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('review_marketing_agreed_at', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('review_marketing_withdrawn_at', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('deleted_at', sa.DateTime(), nullable=True))

    op.create_table(
        'withdrawn_users',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('login_id', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=True),
        sa.Column('phone', sa.String(length=20), nullable=False),
        sa.Column('email', sa.String(length=100), nullable=False),
        sa.Column('withdrawn_at', sa.DateTime(), nullable=False),
        sa.Column('purge_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id']),
        sa.PrimaryKeyConstraint('user_id'),
    )
    op.create_index('ix_withdrawn_users_purge_at', 'withdrawn_users', ['purge_at'])

    op.create_table(
        'admin_access_logs',
        sa.Column('log_id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('admin_id', sa.Integer(), nullable=False),
        sa.Column('accessed_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('ip', sa.String(length=45), nullable=True),
        sa.Column('method', sa.String(length=10), nullable=False),
        sa.Column('action', sa.String(length=10), nullable=False),
        sa.Column('path', sa.String(length=500), nullable=False),
        sa.Column('user_agent', sa.String(length=300), nullable=True),
        sa.PrimaryKeyConstraint('log_id'),
    )
    op.create_index('ix_admin_access_logs_admin_id', 'admin_access_logs', ['admin_id'])
    op.create_index('ix_admin_access_logs_accessed_at', 'admin_access_logs', ['accessed_at'])

    op.alter_column(
        "point_transactions", "reason",
        existing_type=sa.Enum(*OLD_REASONS, name="point_transaction_reason"),
        type_=sa.Enum(*NEW_REASONS, name="point_transaction_reason"),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DELETE FROM point_transactions WHERE reason = 'withdrawal'")
    op.alter_column(
        "point_transactions", "reason",
        existing_type=sa.Enum(*NEW_REASONS, name="point_transaction_reason"),
        type_=sa.Enum(*OLD_REASONS, name="point_transaction_reason"),
        existing_nullable=False,
    )
    op.drop_index('ix_admin_access_logs_accessed_at', table_name='admin_access_logs')
    op.drop_index('ix_admin_access_logs_admin_id', table_name='admin_access_logs')
    op.drop_table('admin_access_logs')
    op.drop_index('ix_withdrawn_users_purge_at', table_name='withdrawn_users')
    op.drop_table('withdrawn_users')
    op.drop_column('users', 'deleted_at')
    op.drop_column('users', 'review_marketing_withdrawn_at')
    op.drop_column('users', 'review_marketing_agreed_at')
    op.drop_column('users', 'age_14_confirmed_at')
    op.drop_column('users', 'terms_agreed_at')
