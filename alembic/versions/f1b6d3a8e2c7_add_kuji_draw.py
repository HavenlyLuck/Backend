"""add kuji draw: board version, kuji storage items, kuji_draw point reason

Revision ID: f1b6d3a8e2c7
Revises: e5a9c2d7f3b4
Create Date: 2026-10-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1b6d3a8e2c7'
down_revision: Union[str, Sequence[str], None] = 'e5a9c2d7f3b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


OLD_REASONS = ("raffle_entry", "store_purchase", "admin_grant", "refund", "raffle_consolation", "avatar_purchase")
NEW_REASONS = OLD_REASONS + ("kuji_draw",)
OLD_SOURCES = ("raffle", "store")
NEW_SOURCES = OLD_SOURCES + ("kuji",)


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('kuji_sets', sa.Column('board_version', sa.Integer(), server_default='1', nullable=False))

    op.alter_column(
        "storage_items", "source",
        existing_type=sa.Enum(*OLD_SOURCES, name="storage_source"),
        type_=sa.Enum(*NEW_SOURCES, name="storage_source"),
        existing_nullable=False,
    )
    op.add_column('storage_items', sa.Column('kuji_set_id', sa.Integer(), nullable=True))
    op.add_column('storage_items', sa.Column('kuji_prize_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_storage_items_kuji_set_id', 'storage_items', 'kuji_sets', ['kuji_set_id'], ['kuji_set_id'])
    op.create_foreign_key('fk_storage_items_kuji_prize_id', 'storage_items', 'kuji_prizes', ['kuji_prize_id'], ['kuji_prize_id'])

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
    op.drop_constraint('fk_storage_items_kuji_prize_id', 'storage_items', type_='foreignkey')
    op.drop_constraint('fk_storage_items_kuji_set_id', 'storage_items', type_='foreignkey')
    op.drop_column('storage_items', 'kuji_prize_id')
    op.drop_column('storage_items', 'kuji_set_id')
    op.alter_column(
        "storage_items", "source",
        existing_type=sa.Enum(*NEW_SOURCES, name="storage_source"),
        type_=sa.Enum(*OLD_SOURCES, name="storage_source"),
        existing_nullable=False,
    )
    op.drop_column('kuji_sets', 'board_version')
