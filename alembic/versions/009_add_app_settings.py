"""Add app_settings: runtime settings an admin can change without a deploy.

* app_settings: key/value rows. Only "ai_model" ({"provider", "model"}) today -
  the AI provider and model selected in /admin/settings. A missing row means
  the environment default: Gemini with GEMINI_MODEL (AI_PROVIDER is ignored -
  Claude is only ever chosen in /admin/settings). Never holds secrets; API
  keys stay in the environment.

Revision ID: 009
Revises: 008
Create Date: 2026-10-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# Revision identifiers, used by Alembic.
revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_by", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("app_settings")
