"""아바타 아이디어 공모전 응모작 좋아요

- idea_contest_likes: 한 계정이 한 응모작에 한 번 (entry_id + user_id 유일)

Revision ID: a2c4e6b8d0f1
Revises: f3a5c7e9b2d4
Create Date: 2026-11-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a2c4e6b8d0f1'
down_revision: Union[str, Sequence[str], None] = 'f3a5c7e9b2d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "idea_contest_likes",
        sa.Column("like_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("entry_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["entry_id"], ["idea_contest_entries.entry_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("like_id"),
        sa.UniqueConstraint("entry_id", "user_id", name="uq_idea_contest_like"),
    )
    op.create_index(op.f("ix_idea_contest_likes_entry_id"), "idea_contest_likes", ["entry_id"], unique=False)
    op.create_index(op.f("ix_idea_contest_likes_user_id"), "idea_contest_likes", ["user_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_idea_contest_likes_user_id"), table_name="idea_contest_likes")
    op.drop_index(op.f("ix_idea_contest_likes_entry_id"), table_name="idea_contest_likes")
    op.drop_table("idea_contest_likes")
