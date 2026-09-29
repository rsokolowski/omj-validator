"""Add private tasks ("Moje zadania") and AI usage accounting.

A student can add their own tasks - from a photo of a booklet page or typed in -
and have handwritten solutions graded like OMJ tasks. Consequences for the
schema and for RODO:

* private_tasks: owned by one user, cascades with the account (art. 17) and
  expires 24 months after the last activity (art. 5(1)(e),
  retention_private_task_months). The statement may be third-party material,
  so it is never shared or listed - only the owner reads it.
* submissions now reference EITHER an OMJ task (year, etap, task_number) OR a
  private task (private_task_id), enforced by a check constraint so no OMJ
  aggregate can ever pick up a private row by accident.
* ai_usage: one content-free row per non-submission AI call (extraction, hint
  generation), so those calls are rate limited like submissions. Expires after
  retention_ai_usage_days.
* deleted_account_quota.ai_usage_count: erasing an account must not reset the
  new limits either (see DeletedAccountQuotaDB).

Revision ID: 006
Revises: 005
Create Date: 2026-09-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# Revision identifiers, used by Alembic.
revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TASK_REF_CHECK = (
    "(year IS NOT NULL AND etap IS NOT NULL AND task_number IS NOT NULL "
    "AND private_task_id IS NULL) OR "
    "(year IS NULL AND etap IS NULL AND task_number IS NULL "
    "AND private_task_id IS NOT NULL)"
)


def upgrade() -> None:
    op.create_table(
        "private_tasks",
        sa.Column("id", sa.String(length=12), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_label", sa.String(length=120), nullable=True),
        sa.Column("category", sa.String(length=20), nullable=True),
        sa.Column("difficulty", sa.Integer(), nullable=True),
        sa.Column("hints", sa.JSON(), nullable=False),
        sa.Column("hints_revealed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pending_hints_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source_images", sa.JSON(), nullable=False),
        sa.Column("origin", sa.String(length=10), nullable=False),
        sa.Column("extraction_meta", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("last_activity_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.google_sub"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_private_tasks_user_id", "private_tasks", ["user_id"])
    op.create_index("ix_private_tasks_last_activity_at", "private_tasks", ["last_activity_at"])
    op.create_index(
        "ix_private_tasks_user_activity", "private_tasks", ["user_id", "last_activity_at"]
    )

    op.create_table(
        "ai_usage",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("meta", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.google_sub"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_usage_user_id", "ai_usage", ["user_id"])
    op.create_index("ix_ai_usage_created_at", "ai_usage", ["created_at"])

    op.alter_column("submissions", "year", existing_type=sa.String(length=10), nullable=True)
    op.alter_column("submissions", "etap", existing_type=sa.String(length=10), nullable=True)
    op.alter_column("submissions", "task_number", existing_type=sa.Integer(), nullable=True)
    op.add_column(
        "submissions", sa.Column("private_task_id", sa.String(length=12), nullable=True)
    )
    op.add_column(
        "submissions",
        sa.Column("hints_used", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_foreign_key(
        "fk_submissions_private_task_id",
        "submissions",
        "private_tasks",
        ["private_task_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_check_constraint("ck_submissions_task_ref", "submissions", TASK_REF_CHECK)
    op.create_index(
        "ix_submissions_user_private_task", "submissions", ["user_id", "private_task_id"]
    )

    op.add_column(
        "deleted_account_quota",
        sa.Column("ai_usage_count", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("deleted_account_quota", "ai_usage_count")

    # Private submissions cannot satisfy NOT NULL year/etap/task_number
    op.execute("DELETE FROM submissions WHERE private_task_id IS NOT NULL")
    op.drop_index("ix_submissions_user_private_task", table_name="submissions")
    op.drop_constraint("ck_submissions_task_ref", "submissions", type_="check")
    op.drop_constraint("fk_submissions_private_task_id", "submissions", type_="foreignkey")
    op.drop_column("submissions", "hints_used")
    op.drop_column("submissions", "private_task_id")
    op.alter_column("submissions", "task_number", existing_type=sa.Integer(), nullable=False)
    op.alter_column("submissions", "etap", existing_type=sa.String(length=10), nullable=False)
    op.alter_column("submissions", "year", existing_type=sa.String(length=10), nullable=False)

    op.drop_index("ix_ai_usage_created_at", table_name="ai_usage")
    op.drop_index("ix_ai_usage_user_id", table_name="ai_usage")
    op.drop_table("ai_usage")

    op.drop_index("ix_private_tasks_user_activity", table_name="private_tasks")
    op.drop_index("ix_private_tasks_last_activity_at", table_name="private_tasks")
    op.drop_index("ix_private_tasks_user_id", table_name="private_tasks")
    op.drop_table("private_tasks")
