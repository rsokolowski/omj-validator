"""Add rate-limit tombstones for erased accounts.

Self-service account deletion (RODO art. 17) removes the submission rows the
24h rate limits are counted from, which would let a user reset their quota by
deleting and re-creating the account. This table keeps a salted, irreversible
digest plus the used quota until the window closes.

Revision ID: 004
Revises: 003
Create Date: 2026-08-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# Revision identifiers, used by Alembic.
revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "deleted_account_quota",
        sa.Column("user_hash", sa.String(length=64), nullable=False),
        sa.Column("submission_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("oldest_submission_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("user_hash"),
    )
    op.create_index(
        "ix_deleted_account_quota_expires_at",
        "deleted_account_quota",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_deleted_account_quota_expires_at",
        table_name="deleted_account_quota",
    )
    op.drop_table("deleted_account_quota")
