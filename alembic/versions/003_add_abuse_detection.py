"""Add abuse detection columns to submissions.

Revision ID: 003
Revises: 002
Create Date: 2025-12-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# Revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create issue_type enum
    issue_type_enum = sa.Enum('none', 'wrong_task', 'injection', name='issuetype')
    issue_type_enum.create(op.get_bind(), checkfirst=True)

    # Add issue_type column with default 'none'
    op.add_column(
        'submissions',
        sa.Column(
            'issue_type',
            issue_type_enum,
            nullable=False,
            server_default='none'
        )
    )

    # Add abuse_score column with default 0
    op.add_column(
        'submissions',
        sa.Column(
            'abuse_score',
            sa.Integer(),
            nullable=False,
            server_default='0'
        )
    )

    # Create index on issue_type for admin filtering
    op.create_index('ix_submissions_issue_type', 'submissions', ['issue_type'])


def downgrade() -> None:
    # Drop index
    op.drop_index('ix_submissions_issue_type', table_name='submissions')

    # Drop columns
    op.drop_column('submissions', 'abuse_score')
    op.drop_column('submissions', 'issue_type')

    # Drop enum type
    issue_type_enum = sa.Enum('none', 'wrong_task', 'injection', name='issuetype')
    issue_type_enum.drop(op.get_bind(), checkfirst=True)
