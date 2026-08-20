"""Add the admin access audit trail.

RODO art. 5(2) (accountability): an admin can read every submission and every
uploaded photo, so that access has to leave a record. The table holds
identifiers and a resource label only - never any content - and expires via
retention_admin_audit_months.

Revision ID: 005
Revises: 004
Create Date: 2026-08-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# Revision identifiers, used by Alembic.
revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "admin_access_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("admin_email", sa.String(length=255), nullable=False),
        sa.Column("subject_user_id", sa.String(length=255), nullable=True),
        sa.Column("resource", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_admin_access_log_admin_email", "admin_access_log", ["admin_email"])
    op.create_index("ix_admin_access_log_subject_user_id", "admin_access_log", ["subject_user_id"])
    op.create_index("ix_admin_access_log_created_at", "admin_access_log", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_admin_access_log_created_at", table_name="admin_access_log")
    op.drop_index("ix_admin_access_log_subject_user_id", table_name="admin_access_log")
    op.drop_index("ix_admin_access_log_admin_email", table_name="admin_access_log")
    op.drop_table("admin_access_log")
