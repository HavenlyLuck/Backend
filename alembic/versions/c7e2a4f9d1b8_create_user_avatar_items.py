"""create user_avatar_items and add avatar_purchase point reason

Revision ID: c7e2a4f9d1b8
Revises: a9c4e1f7b2d6
Create Date: 2026-10-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7e2a4f9d1b8'
down_revision: Union[str, Sequence[str], None] = 'a9c4e1f7b2d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


OLD_REASONS = ("raffle_entry", "store_purchase", "admin_grant", "refund", "raffle_consolation")
NEW_REASONS = OLD_REASONS + ("avatar_purchase",)


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('user_avatar_items',
    sa.Column('user_avatar_item_id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('item_id', sa.String(length=50), nullable=False),
    sa.Column('price', sa.Integer(), nullable=False),
    sa.Column('purchased_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ),
    sa.PrimaryKeyConstraint('user_avatar_item_id'),
    sa.UniqueConstraint('user_id', 'item_id', name='uq_user_avatar_item')
    )
    # 아바타 아이템 구매 차감 사유 추가
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
    op.drop_table('user_avatar_items')
