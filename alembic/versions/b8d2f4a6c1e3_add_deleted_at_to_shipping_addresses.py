"""add deleted_at to shipping_addresses

배송지는 5개까지만 보이고, 넘치면 기본이 아닌 오래된 배송지부터 숨긴다 (배송 신청 내역이 참조하므로 행은 남긴다)

Revision ID: b8d2f4a6c1e3
Revises: a3c7e9b1d5f2
Create Date: 2026-10-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b8d2f4a6c1e3'
down_revision: Union[str, Sequence[str], None] = 'a3c7e9b1d5f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('shipping_addresses', sa.Column('deleted_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('shipping_addresses', 'deleted_at')
