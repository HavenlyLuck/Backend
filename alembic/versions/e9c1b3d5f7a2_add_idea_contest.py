"""아바타 아이디어 공모전

- idea_contest_entries: 응모작 (그림 · 아이디어 이름 · 설명, 주 단위, 등수 · 가림)
- idea_contest_weeks: 시상을 마친 주 (같은 주 두 번 지급 방지)
- free_tickets.kind: idea_contest (수상 쌀 응모권, 1등 10장 · 2·3등 5장)

Revision ID: e9c1b3d5f7a2
Revises: d7a2c4e6f8b1
Create Date: 2026-11-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e9c1b3d5f7a2'
down_revision: Union[str, Sequence[str], None] = 'd7a2c4e6f8b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


OLD_KINDS = ("first_purchase", "referral", "signup_event", "store_purchase")
NEW_KINDS = OLD_KINDS + ("idea_contest",)


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "idea_contest_entries",
        sa.Column("entry_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("title", sa.String(length=40), nullable=False),
        sa.Column("description", sa.String(length=300), nullable=True),
        sa.Column("image_url", sa.String(length=500), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("hidden_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("entry_id"),
    )
    op.create_index(op.f("ix_idea_contest_entries_user_id"), "idea_contest_entries", ["user_id"], unique=False)
    op.create_index(op.f("ix_idea_contest_entries_week_start"), "idea_contest_entries", ["week_start"], unique=False)
    op.create_table(
        "idea_contest_weeks",
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("awarded_at", sa.DateTime(), nullable=False),
        sa.Column("awarded_by", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["awarded_by"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("week_start"),
    )
    op.alter_column(
        "free_tickets", "kind",
        existing_type=sa.Enum(*OLD_KINDS, name="free_ticket_kind"),
        type_=sa.Enum(*NEW_KINDS, name="free_ticket_kind"),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DELETE FROM free_tickets WHERE kind = 'idea_contest' AND raffle_entry_id IS NULL")
    op.alter_column(
        "free_tickets", "kind",
        existing_type=sa.Enum(*NEW_KINDS, name="free_ticket_kind"),
        type_=sa.Enum(*OLD_KINDS, name="free_ticket_kind"),
        existing_nullable=False,
    )
    op.drop_table("idea_contest_weeks")
    op.drop_index(op.f("ix_idea_contest_entries_week_start"), table_name="idea_contest_entries")
    op.drop_index(op.f("ix_idea_contest_entries_user_id"), table_name="idea_contest_entries")
    op.drop_table("idea_contest_entries")
