"""Add submissions.solution_text - a typed solution next to, or instead of, photos.

Students who work on a computer or tablet can type their solution (plain text
with $LaTeX$ formulas, optionally drawings made in the browser, which arrive
as PNG photos). The text is the student's content like the photos: same
retention (retention_submission_months), same erasure on account deletion, and
it goes to Google for grading. No backfill, no index; NULL means photos only.

Revision ID: 007
Revises: 006
Create Date: 2026-09-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# Revision identifiers, used by Alembic.
revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("submissions", sa.Column("solution_text", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("submissions", "solution_text")
