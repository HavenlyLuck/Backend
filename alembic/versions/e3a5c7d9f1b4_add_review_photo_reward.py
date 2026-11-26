"""사진 후기 쌀 응모권 보상

- free_tickets.kind: review_photo (사진 후기 1건당 쌀 응모권 1장)
- storage_items.review_rewarded_at: 그 보관함 상품으로 보상을 준 시각 — 후기를 지우고 다시 써도 또 주지 않게 후기와 따로 남긴다

Revision ID: e3a5c7d9f1b4
Revises: d8f0b2c4e6a7
Create Date: 2026-11-26 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e3a5c7d9f1b4'
down_revision: Union[str, Sequence[str], None] = 'd8f0b2c4e6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


OLD_KINDS = ("first_purchase", "referral", "signup_event", "store_purchase", "idea_contest", "storage_convert")
NEW_KINDS = OLD_KINDS + ("review_photo",)


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "free_tickets", "kind",
        existing_type=sa.Enum(*OLD_KINDS, name="free_ticket_kind"),
        type_=sa.Enum(*NEW_KINDS, name="free_ticket_kind"),
        existing_nullable=False,
    )
    op.add_column("storage_items", sa.Column("review_rewarded_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("storage_items", "review_rewarded_at")
    op.execute("DELETE FROM free_tickets WHERE kind = 'review_photo' AND raffle_entry_id IS NULL")
    op.alter_column(
        "free_tickets", "kind",
        existing_type=sa.Enum(*NEW_KINDS, name="free_ticket_kind"),
        type_=sa.Enum(*OLD_KINDS, name="free_ticket_kind"),
        existing_nullable=False,
    )
