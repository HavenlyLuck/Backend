"""create raffle_entries and point_transactions tables

Revision ID: c3d8a6f2e4b1
Revises: b1f4e7c9a2d3
Create Date: 2026-08-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d8a6f2e4b1'
down_revision: Union[str, Sequence[str], None] = 'b1f4e7c9a2d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('raffle_entries',
    sa.Column('entry_id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('raffle_product_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('ticket_count', sa.Integer(), nullable=False),
    sa.Column('points_spent', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['raffle_product_id'], ['raffle_products.raffle_product_id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ),
    sa.PrimaryKeyConstraint('entry_id')
    )

    op.create_table('point_transactions',
    sa.Column('transaction_id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('point_type', sa.Enum('woon', 'ssal', name='point_transaction_type'), nullable=False),
    sa.Column('amount', sa.Integer(), nullable=False),
    sa.Column('balance_after', sa.Integer(), nullable=False),
    sa.Column('reason', sa.Enum('raffle_entry', 'store_purchase', 'admin_grant', 'refund', name='point_transaction_reason'), nullable=False),
    sa.Column('reference_id', sa.Integer(), nullable=True),
    sa.Column('description', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ),
    sa.PrimaryKeyConstraint('transaction_id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('point_transactions')
    op.drop_table('raffle_entries')
