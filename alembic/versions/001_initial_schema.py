"""Initial schema with users and submissions tables.

Revision ID: 001
Revises:
Create Date: 2025-12-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# Revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        "users",
        sa.Column("google_sub", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("google_sub"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # Create submissions table
    op.create_table(
        "submissions",
        sa.Column("id", sa.String(8), nullable=False),
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column("year", sa.String(10), nullable=False),
        sa.Column("etap", sa.String(10), nullable=False),
        sa.Column("task_number", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("PENDING", "PROCESSING", "COMPLETED", "FAILED", name="submissionstatus"),
            nullable=False,
        ),
        sa.Column("images", sa.JSON(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("scoring_meta", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.google_sub"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_submissions_user_id", "submissions", ["user_id"])
    op.create_index(
        "ix_submissions_user_task",
        "submissions",
        ["user_id", "year", "etap", "task_number"],
    )
    op.create_index(
        "ix_submissions_task",
        "submissions",
        ["year", "etap", "task_number"],
    )


def downgrade() -> None:
    # Drop submissions table
    op.drop_index("ix_submissions_task", table_name="submissions")
    op.drop_index("ix_submissions_user_task", table_name="submissions")
    op.drop_index("ix_submissions_user_id", table_name="submissions")
    op.drop_table("submissions")

    # Drop users table
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

    # Drop enum type
    op.execute("DROP TYPE IF EXISTS submissionstatus")
