"""shift entry_number to start at 1 instead of 0

Revision ID: 8149114268c7
Revises: 362e9f87e792
Create Date: 2026-08-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '8149114268c7'
down_revision: Union[str, Sequence[str], None] = '362e9f87e792'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("UPDATE raffle_entries SET entry_number = entry_number + 1")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("UPDATE raffle_entries SET entry_number = entry_number - 1")
