"""Add patterns ("Wzorce"): problem-solving patterns with spaced repetition.

A student writes down patterns ("when I see X in a problem, try Y"), refines
them with the AI, links them to tasks and reviews them on a schedule.

* patterns: owned by one user, cascades with the account (art. 17) and expires
  24 months after the last activity (art. 5(1)(e), retention_pattern_months).
* pattern_links: a task connected to a pattern - EITHER an OMJ task key OR a
  private task (check constraint); deleted with the pattern or the private task.
* pattern_reviews: one row per recall card or graded practice task.
* submissions.pattern_id: the pattern a solution practised; SET NULL when the
  pattern is deleted, the submission itself stays.

Revision ID: 008
Revises: 007
Create Date: 2026-09-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# Revision identifiers, used by Alembic.
revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


LINK_REF_CHECK = (
    "(task_key IS NOT NULL AND private_task_id IS NULL) OR "
    "(task_key IS NULL AND private_task_id IS NOT NULL)"
)


def upgrade() -> None:
    op.create_table(
        "patterns",
        sa.Column("id", sa.String(length=12), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("trigger", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("example", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=20), nullable=True),
        sa.Column("skills", sa.JSON(), nullable=False),
        sa.Column("origin", sa.String(length=16), nullable=False),
        sa.Column("refinement", sa.JSON(), nullable=False),
        sa.Column("srs_level", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.Column("srs_streak", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("due_on", sa.Date(), nullable=False),
        sa.Column("review_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lapse_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("last_activity_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.google_sub"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_patterns_user_id", "patterns", ["user_id"])
    op.create_index("ix_patterns_due_on", "patterns", ["due_on"])
    op.create_index("ix_patterns_last_activity_at", "patterns", ["last_activity_at"])
    op.create_index("ix_patterns_user_due", "patterns", ["user_id", "due_on"])

    op.create_table(
        "pattern_links",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("pattern_id", sa.String(length=12), nullable=False),
        sa.Column("task_key", sa.String(length=32), nullable=True),
        sa.Column("private_task_id", sa.String(length=12), nullable=True),
        sa.Column("role", sa.String(length=10), nullable=False),
        sa.Column("origin", sa.String(length=8), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["pattern_id"], ["patterns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["private_task_id"], ["private_tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(LINK_REF_CHECK, name="ck_pattern_links_ref"),
        sa.UniqueConstraint("pattern_id", "task_key", name="uq_pattern_links_task_key"),
        sa.UniqueConstraint("pattern_id", "private_task_id", name="uq_pattern_links_private_task"),
    )
    op.create_index("ix_pattern_links_pattern_id", "pattern_links", ["pattern_id"])
    op.create_index("ix_pattern_links_task_key", "pattern_links", ["task_key"])
    op.create_index("ix_pattern_links_private_task_id", "pattern_links", ["private_task_id"])

    op.add_column("submissions", sa.Column("pattern_id", sa.String(length=12), nullable=True))
    op.create_foreign_key(
        "fk_submissions_pattern_id",
        "submissions",
        "patterns",
        ["pattern_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_submissions_pattern_id", "submissions", ["pattern_id"])

    op.create_table(
        "pattern_reviews",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("pattern_id", sa.String(length=12), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("kind", sa.String(length=8), nullable=False),
        sa.Column("outcome", sa.String(length=8), nullable=False),
        sa.Column("recall_text", sa.Text(), nullable=True),
        sa.Column("submission_id", sa.String(length=8), nullable=True),
        sa.Column("level_before", sa.SmallInteger(), nullable=False),
        sa.Column("level_after", sa.SmallInteger(), nullable=False),
        sa.Column("due_before", sa.Date(), nullable=False),
        sa.Column("due_after", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["pattern_id"], ["patterns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.google_sub"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["submission_id"], ["submissions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pattern_reviews_pattern_id", "pattern_reviews", ["pattern_id"])
    op.create_index("ix_pattern_reviews_submission_id", "pattern_reviews", ["submission_id"])


def downgrade() -> None:
    op.drop_index("ix_pattern_reviews_submission_id", table_name="pattern_reviews")
    op.drop_index("ix_pattern_reviews_pattern_id", table_name="pattern_reviews")
    op.drop_table("pattern_reviews")

    op.drop_index("ix_submissions_pattern_id", table_name="submissions")
    op.drop_constraint("fk_submissions_pattern_id", "submissions", type_="foreignkey")
    op.drop_column("submissions", "pattern_id")

    op.drop_index("ix_pattern_links_private_task_id", table_name="pattern_links")
    op.drop_index("ix_pattern_links_task_key", table_name="pattern_links")
    op.drop_index("ix_pattern_links_pattern_id", table_name="pattern_links")
    op.drop_table("pattern_links")

    op.drop_index("ix_patterns_user_due", table_name="patterns")
    op.drop_index("ix_patterns_last_activity_at", table_name="patterns")
    op.drop_index("ix_patterns_due_on", table_name="patterns")
    op.drop_index("ix_patterns_user_id", table_name="patterns")
    op.drop_table("patterns")
