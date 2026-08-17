"""create store_products table

Revision ID: b1f4e7c9a2d3
Revises: 3a646d3f63da
Create Date: 2026-08-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b1f4e7c9a2d3'
down_revision: Union[str, Sequence[str], None] = '3a646d3f63da'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('store_products',
    sa.Column('store_product_id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('admin_id', sa.Integer(), nullable=False),
    sa.Column('product_name', sa.String(length=200), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('point_type', sa.Enum('woon', 'ssal', name='store_point_type'), nullable=False),
    sa.Column('price', sa.Integer(), nullable=False),
    sa.Column('stock', sa.Integer(), nullable=False),
    sa.Column('image_url', sa.String(length=500), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['admin_id'], ['users.user_id'], ),
    sa.PrimaryKeyConstraint('store_product_id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('store_products')
