"""add sold_out_at to kuji_sets, deleted_at to store_products

Revision ID: a9d4f2c6b8e1
Revises: e3a7c5b9d1f6
Create Date: 2026-11-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a9d4f2c6b8e1'
down_revision: Union[str, Sequence[str], None] = 'e3a7c5b9d1f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('kuji_sets', sa.Column('sold_out_at', sa.DateTime(), nullable=True))
    # 이미 매진된 쿠지는 마지막 제비가 뽑힌 시각을 매진 시각으로 채운다
    op.execute(
        """
        UPDATE kuji_sets ks
        JOIN (SELECT kuji_set_id, MAX(drawn_at) AS last_drawn FROM kuji_tickets GROUP BY kuji_set_id) t
          ON t.kuji_set_id = ks.kuji_set_id
        SET ks.sold_out_at = t.last_drawn
        WHERE ks.remaining_tickets = 0
        """
    )
    op.add_column('store_products', sa.Column('deleted_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('store_products', 'deleted_at')
    op.drop_column('kuji_sets', 'sold_out_at')
