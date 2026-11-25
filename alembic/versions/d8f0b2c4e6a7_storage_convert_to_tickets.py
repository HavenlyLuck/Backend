"""보관 기한 지난 상품을 쌀포인트 대신 쌀 응모권으로 전환

- free_tickets.kind: storage_convert (응모 당첨: 정가 ÷ 2,000원, 쿠지: 원가 × 1.3 ÷ 2,000원 — 올림)
- storage_items.convert_tickets: 전환 때 준 응모권 장수

Revision ID: d8f0b2c4e6a7
Revises: c6e8a0b2d4f5
Create Date: 2026-11-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd8f0b2c4e6a7'
down_revision: Union[str, Sequence[str], None] = 'c6e8a0b2d4f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


OLD_KINDS = ("first_purchase", "referral", "signup_event", "store_purchase", "idea_contest")
NEW_KINDS = OLD_KINDS + ("storage_convert",)


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "free_tickets", "kind",
        existing_type=sa.Enum(*OLD_KINDS, name="free_ticket_kind"),
        type_=sa.Enum(*NEW_KINDS, name="free_ticket_kind"),
        existing_nullable=False,
    )
    op.add_column("storage_items", sa.Column("convert_tickets", sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("storage_items", "convert_tickets")
    op.execute("DELETE FROM free_tickets WHERE kind = 'storage_convert' AND raffle_entry_id IS NULL")
    op.alter_column(
        "free_tickets", "kind",
        existing_type=sa.Enum(*NEW_KINDS, name="free_ticket_kind"),
        type_=sa.Enum(*OLD_KINDS, name="free_ticket_kind"),
        existing_nullable=False,
    )
