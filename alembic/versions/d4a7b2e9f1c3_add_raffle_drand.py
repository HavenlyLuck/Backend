"""응모 추첨에 drand 공개 난수 기록

- raffle_products: drand_round, drand_randomness, drand_signature

Revision ID: d4a7b2e9f1c3
Revises: f2c8e4a6b1d9
Create Date: 2026-11-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4a7b2e9f1c3'
down_revision: Union[str, Sequence[str], None] = 'f2c8e4a6b1d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('raffle_products', sa.Column('drand_round', sa.Integer(), nullable=True))
    op.add_column('raffle_products', sa.Column('drand_randomness', sa.String(length=64), nullable=True))
    op.add_column('raffle_products', sa.Column('drand_signature', sa.String(length=192), nullable=True))


def downgrade() -> None:
    op.drop_column('raffle_products', 'drand_signature')
    op.drop_column('raffle_products', 'drand_randomness')
    op.drop_column('raffle_products', 'drand_round')
