"""오픈 이벤트 가입 선물 쌀 응모권

- free_tickets.kind: signup_event (오픈 이벤트 기간에 가입하면 1장)

Revision ID: b2f6d9e4a7c3
Revises: e7b3c9d1a4f6
Create Date: 2026-11-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2f6d9e4a7c3'
down_revision: Union[str, Sequence[str], None] = 'e7b3c9d1a4f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


OLD_KINDS = ("first_purchase", "referral")
NEW_KINDS = OLD_KINDS + ("signup_event",)


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
    op.execute("DELETE FROM free_tickets WHERE kind = 'signup_event' AND raffle_entry_id IS NULL")
    op.alter_column(
        "free_tickets", "kind",
        existing_type=sa.Enum(*NEW_KINDS, name="free_ticket_kind"),
        type_=sa.Enum(*OLD_KINDS, name="free_ticket_kind"),
        existing_nullable=False,
    )
