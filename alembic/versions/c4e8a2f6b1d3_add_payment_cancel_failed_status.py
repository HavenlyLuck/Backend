"""add cancel_failed to payment status (자동 환불이 불가능한 결제 — 재시도 중단, 수동 확인)

Revision ID: c4e8a2f6b1d3
Revises: b7c3e9a1d5f4
Create Date: 2026-11-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4e8a2f6b1d3'
down_revision: Union[str, Sequence[str], None] = 'b7c3e9a1d5f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OLD = ('pending', 'paid', 'cancel_requested', 'cancelled', 'failed')
NEW = OLD + ('cancel_failed',)


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        'payments', 'status',
        existing_type=sa.Enum(*OLD, name='payment_status'),
        type_=sa.Enum(*NEW, name='payment_status'),
        existing_nullable=False,
        existing_server_default='pending',
    )


def downgrade() -> None:
    """Downgrade schema."""
    # 되돌리기 전에 cancel_failed 결제를 cancel_requested로 돌려 둔다 (다시 재시도 대상이 됨)
    op.execute("UPDATE payments SET status = 'cancel_requested' WHERE status = 'cancel_failed'")
    op.alter_column(
        'payments', 'status',
        existing_type=sa.Enum(*NEW, name='payment_status'),
        type_=sa.Enum(*OLD, name='payment_status'),
        existing_nullable=False,
        existing_server_default='pending',
    )
