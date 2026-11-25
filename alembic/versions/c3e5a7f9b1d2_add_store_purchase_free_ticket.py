"""쌀포인트 상점에서 산 쌀 응모권

- free_tickets.kind: store_purchase (쌀포인트 상점 쿠폰 구매, 계정당 한 주에 2장까지)

Revision ID: c3e5a7f9b1d2
Revises: b7d1e9a3c5f2
Create Date: 2026-11-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3e5a7f9b1d2'
down_revision: Union[str, Sequence[str], None] = 'b7d1e9a3c5f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


OLD_KINDS = ("first_purchase", "referral", "signup_event")
NEW_KINDS = OLD_KINDS + ("store_purchase",)


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "free_tickets", "kind",
        existing_type=sa.Enum(*OLD_KINDS, name="free_ticket_kind"),
        type_=sa.Enum(*NEW_KINDS, name="free_ticket_kind"),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DELETE FROM free_tickets WHERE kind = 'store_purchase' AND raffle_entry_id IS NULL")
    op.alter_column(
        "free_tickets", "kind",
        existing_type=sa.Enum(*NEW_KINDS, name="free_ticket_kind"),
        type_=sa.Enum(*OLD_KINDS, name="free_ticket_kind"),
        existing_nullable=False,
    )
