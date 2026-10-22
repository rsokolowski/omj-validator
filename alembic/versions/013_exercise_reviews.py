"""Exercise-based pattern reviews.

* private_tasks.solution: worked solution of a generated exercise.
* private_tasks.rejected_at: exercise marked as broken, never offered again.
* pattern_reviews.private_task_id / trigger_shown: the exercise a review used
  and whether the trigger was visible.

Revision ID: 013
Revises: 012
Create Date: 2026-10-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# Revision identifiers, used by Alembic.
revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("private_tasks", sa.Column("solution", sa.Text(), nullable=True))
    op.add_column("private_tasks", sa.Column("rejected_at", sa.DateTime(), nullable=True))
    op.add_column("pattern_reviews", sa.Column("private_task_id", sa.String(length=12), nullable=True))
    op.add_column("pattern_reviews", sa.Column("trigger_shown", sa.Boolean(), nullable=True))
    op.create_foreign_key(
        "fk_pattern_reviews_private_task_id",
        "pattern_reviews",
        "private_tasks",
        ["private_task_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_pattern_reviews_private_task_id", "pattern_reviews", ["private_task_id"])


def downgrade() -> None:
    op.drop_index("ix_pattern_reviews_private_task_id", table_name="pattern_reviews")
    op.drop_constraint("fk_pattern_reviews_private_task_id", "pattern_reviews", type_="foreignkey")
    op.drop_column("pattern_reviews", "trigger_shown")
    op.drop_column("pattern_reviews", "private_task_id")
    op.drop_column("private_tasks", "rejected_at")
    op.drop_column("private_tasks", "solution")
