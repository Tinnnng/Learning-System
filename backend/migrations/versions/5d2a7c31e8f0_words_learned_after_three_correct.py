"""words learned after three correct answers in a row

Revision ID: 5d2a7c31e8f0
Revises: 09957b5baa95
Create Date: 2026-10-12 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '5d2a7c31e8f0'
down_revision: Union[str, Sequence[str], None] = '09957b5baa95'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """New rule (2026-10-12): a word never answered wrong is learned after 3 correct answers in a row.

    Data only: mark existing words that already qualify, and drop their review cards
    (learned words are no longer scheduled).
    """
    op.execute(
        "UPDATE word_progress SET mastered_at = last_answered_at "
        "WHERE in_wrong_list = 0 AND mastered_at IS NULL AND correct_streak >= 3"
    )
    op.execute(
        "DELETE FROM srs_card WHERE item_type = 'word' AND item_id IN "
        "(SELECT word_id FROM word_progress WHERE in_wrong_list = 0 AND mastered_at IS NOT NULL)"
    )


def downgrade() -> None:
    """Nothing to undo: the old rule simply ignored mastered_at for these words."""
