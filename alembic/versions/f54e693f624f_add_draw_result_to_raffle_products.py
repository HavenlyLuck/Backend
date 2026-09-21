"""add draw result columns to raffle_products

Revision ID: f54e693f624f
Revises: 8149114268c7
Create Date: 2026-08-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f54e693f624f'
down_revision: Union[str, Sequence[str], None] = '8149114268c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('raffle_products', sa.Column('winner_entry_number', sa.Integer(), nullable=True))
    op.add_column('raffle_products', sa.Column('winner_user_id', sa.Integer(), nullable=True))
    op.add_column('raffle_products', sa.Column('draw_video_url', sa.String(length=500), nullable=True))
    op.create_foreign_key(
        'fk_raffle_products_winner_user_id', 'raffle_products', 'users',
        ['winner_user_id'], ['user_id'],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_raffle_products_winner_user_id', 'raffle_products', type_='foreignkey')
    op.drop_column('raffle_products', 'draw_video_url')
    op.drop_column('raffle_products', 'winner_user_id')
    op.drop_column('raffle_products', 'winner_entry_number')
