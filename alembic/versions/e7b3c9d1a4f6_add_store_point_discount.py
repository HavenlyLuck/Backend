"""결제 상점 쌀포인트 할인

- payments.point_used — 결제 상점 구매 때 할인에 쓴 쌀포인트 (amount는 할인 뒤 카드 결제 금액)
- point_transactions.reason: 할인에 사용(store_discount), 구매 취소로 돌려받음(store_discount_refund)

Revision ID: e7b3c9d1a4f6
Revises: d5e1a8c3f9b2
Create Date: 2026-11-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7b3c9d1a4f6'
down_revision: Union[str, Sequence[str], None] = 'd5e1a8c3f9b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


OLD_REASONS = ("store_purchase", "admin_grant", "raffle_consolation", "avatar_purchase", "withdrawal")
NEW_REASONS = OLD_REASONS + ("store_discount", "store_discount_refund")


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('payments', sa.Column('point_used', sa.Integer(), server_default='0', nullable=False))
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
    op.drop_column('payments', 'point_used')
