"""add raffle_entries.result_checked_at (응모자가 당첨결과를 확인한 시각)

예전에는 '결과 확인함'을 브라우저(localStorage)에만 저장해서, 다른 기기·주소에서 들어가면
이미 본 결과가 다시 '참여 중인 응모'로 떴다. 이제 서버에 기록한다.
기존 데이터: 추첨이 끝난 지 하루가 넘은 응모는 이미 확인한 것으로 채워 둔다.

Revision ID: a7d3e9b1c5f4
Revises: e6a1c8d4f2b7
Create Date: 2026-11-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7d3e9b1c5f4'
down_revision: Union[str, Sequence[str], None] = 'e6a1c8d4f2b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('raffle_entries', sa.Column('result_checked_at', sa.DateTime(), nullable=True))
    op.execute(
        """
        UPDATE raffle_entries e
        JOIN raffle_products p ON p.raffle_product_id = e.raffle_product_id
        SET e.result_checked_at = p.drawn_at
        WHERE p.status = 'completed'
          AND p.winner_entry_number IS NOT NULL
          AND p.drawn_at IS NOT NULL
          AND p.drawn_at < UTC_TIMESTAMP() - INTERVAL 1 DAY
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('raffle_entries', 'result_checked_at')
