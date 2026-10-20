"""Drill exercises for patterns ("Ćwiczenia do wzorca").

* private_tasks.pattern_id / exercise_level / answer: an exercise generated for
  a pattern is an ordinary private task that remembers its pattern, its level
  ("easy" | "medium") and a short final answer. NULL for the student's own
  tasks. Deleting a pattern deletes its exercises in code (with their photos);
  the FK's SET NULL is only the database's fallback.
* pattern_exercise_batches: one background generation (running / done /
  failed), so the UI can show progress and a "ready" popup.

Revision ID: 011
Revises: 010
Create Date: 2026-10-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# Revision identifiers, used by Alembic.
revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("private_tasks", sa.Column("pattern_id", sa.String(length=12), nullable=True))
    op.add_column("private_tasks", sa.Column("exercise_level", sa.String(length=8), nullable=True))
    op.add_column("private_tasks", sa.Column("answer", sa.Text(), nullable=True))
    op.create_foreign_key(
        "fk_private_tasks_pattern_id", "private_tasks", "patterns",
        ["pattern_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index("ix_private_tasks_pattern_id", "private_tasks", ["pattern_id"])

    op.create_table(
        "pattern_exercise_batches",
        sa.Column("id", sa.String(length=12), nullable=False),
        sa.Column("pattern_id", sa.String(length=12), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("requested", sa.Integer(), nullable=False),
        sa.Column("created_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.String(length=32), nullable=True),
        sa.Column("acknowledged", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["pattern_id"], ["patterns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pattern_exercise_batches_pattern_id", "pattern_exercise_batches", ["pattern_id"])
    op.create_index("ix_pattern_exercise_batches_user_id", "pattern_exercise_batches", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_pattern_exercise_batches_user_id", table_name="pattern_exercise_batches")
    op.drop_index("ix_pattern_exercise_batches_pattern_id", table_name="pattern_exercise_batches")
    op.drop_table("pattern_exercise_batches")
    op.drop_index("ix_private_tasks_pattern_id", table_name="private_tasks")
    op.drop_constraint("fk_private_tasks_pattern_id", "private_tasks", type_="foreignkey")
    op.drop_column("private_tasks", "answer")
    op.drop_column("private_tasks", "exercise_level")
    op.drop_column("private_tasks", "pattern_id")
