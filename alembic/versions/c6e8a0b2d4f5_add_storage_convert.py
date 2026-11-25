"""보관함 보관 기한 지난 상품 전환 (처음엔 쌀포인트로 만들었다가 d8f0b2c4e6a7에서 쌀 응모권으로 바뀜)

- storage_items.status: converted (30일 안에 배송 신청하지 않은 응모 당첨·쿠지 상품), converted_at
- point_transactions.reason: storage_convert (지금은 쓰지 않음 — 응모권으로 준다)

Revision ID: c6e8a0b2d4f5
Revises: b4d6f8a0c2e3
Create Date: 2026-11-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c6e8a0b2d4f5'
down_revision: Union[str, Sequence[str], None] = 'b4d6f8a0c2e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


OLD_STATUS = ("ready", "requested", "shipped")
NEW_STATUS = OLD_STATUS + ("converted",)
OLD_REASONS = ("store_purchase", "admin_grant", "raffle_consolation", "avatar_purchase", "withdrawal",
               "store_discount", "store_discount_refund", "kuji_prize")
NEW_REASONS = OLD_REASONS + ("storage_convert",)


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "storage_items", "status",
        existing_type=sa.Enum(*OLD_STATUS, name="storage_status"),
        type_=sa.Enum(*NEW_STATUS, name="storage_status"),
        existing_nullable=False,
        existing_server_default="ready",
    )
    op.add_column("storage_items", sa.Column("converted_at", sa.DateTime(), nullable=True))
    op.alter_column(
        "point_transactions", "reason",
        existing_type=sa.Enum(*OLD_REASONS, name="point_transaction_reason"),
        type_=sa.Enum(*NEW_REASONS, name="point_transaction_reason"),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DELETE FROM point_transactions WHERE reason = 'storage_convert'")
    op.alter_column(
        "point_transactions", "reason",
        existing_type=sa.Enum(*NEW_REASONS, name="point_transaction_reason"),
        type_=sa.Enum(*OLD_REASONS, name="point_transaction_reason"),
        existing_nullable=False,
    )
    op.drop_column("storage_items", "converted_at")
    # 전환된 상품은 되돌릴 상태가 없어 지운다 (쌀포인트 지급 기록도 위에서 지웠다)
    op.execute("DELETE FROM storage_items WHERE status = 'converted'")
    op.alter_column(
        "storage_items", "status",
        existing_type=sa.Enum(*NEW_STATUS, name="storage_status"),
        type_=sa.Enum(*OLD_STATUS, name="storage_status"),
        existing_nullable=False,
        existing_server_default="ready",
    )
