"""add raffle_consolation point reason

Revision ID: 00af52a63ca5
Revises: e20c49188b23
Create Date: 2026-10-03 17:19:00.205020

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '00af52a63ca5'
down_revision: Union[str, Sequence[str], None] = 'e20c49188b23'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


OLD_REASONS = ("raffle_entry", "store_purchase", "admin_grant", "refund")
NEW_REASONS = OLD_REASONS + ("raffle_consolation",)


def upgrade() -> None:
    """Upgrade schema."""
    # 낙첨 보상 쌀포인트 지급 사유 추가
    op.alter_column(
        "point_transactions", "reason",
        existing_type=sa.Enum(*OLD_REASONS, name="point_transaction_reason"),
        type_=sa.Enum(*NEW_REASONS, name="point_transaction_reason"),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "point_transactions", "reason",
        existing_type=sa.Enum(*NEW_REASONS, name="point_transaction_reason"),
        type_=sa.Enum(*OLD_REASONS, name="point_transaction_reason"),
        existing_nullable=False,
    )
