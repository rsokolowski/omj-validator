"""Login accounts, year of birth and parent consent by e-mail.

* users.google_sub -> users.id: the primary key stops being Google's. The
  column is RENAMED, so every existing value stays (for existing users
  ``id == their Google sub``) and no foreign key value changes - PostgreSQL
  foreign keys follow a renamed column, and upload directories named after the
  user id do not move. New users get uuid4().hex.
* users.google_sub (new, nullable, unique): the Google identity, backfilled
  from id for every existing row.
* users.email becomes nullable (login accounts have none); login,
  password_hash (argon2id), birth_year (NULL = not asked yet), status
  (active / pending_parent), pending_since, parent_id, session_version.
* parents: a parent's e-mail address, shared by siblings.
* consents: proof of consent (art. 7(1) RODO) - kind self / parent.
* email_tokens: SHA-256 of the links e-mailed to parents; also the send log
  for the e-mail rate limits.
* login_failures: failed login attempts for the brute-force lockout (24 h).

Revision ID: 010
Revises: 009
Create Date: 2026-10-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# Revision identifiers, used by Alembic.
revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


IDENTITY_CHECK = "google_sub IS NOT NULL OR (login IS NOT NULL AND password_hash IS NOT NULL)"
LOGIN_PARENT_CHECK = "login IS NULL OR parent_id IS NOT NULL"


def upgrade() -> None:
    # --- users: id stops being Google's -----------------------------------
    op.alter_column("users", "google_sub", new_column_name="id")
    op.add_column("users", sa.Column("google_sub", sa.String(255), nullable=True))
    op.execute("UPDATE users SET google_sub = id")
    op.create_unique_constraint("uq_users_google_sub", "users", ["google_sub"])
    op.alter_column("users", "email", existing_type=sa.String(255), nullable=True)

    op.create_table(
        "parents",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("email", name="uq_parents_email"),
    )

    op.add_column("users", sa.Column("login", sa.String(32), nullable=True))
    op.add_column("users", sa.Column("password_hash", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("birth_year", sa.SmallInteger(), nullable=True))
    op.add_column(
        "users",
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
    )
    op.add_column("users", sa.Column("pending_since", sa.DateTime(), nullable=True))
    op.add_column("users", sa.Column("parent_id", sa.String(32), nullable=True))
    op.add_column(
        "users",
        sa.Column("session_version", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_unique_constraint("uq_users_login", "users", ["login"])
    op.create_foreign_key("fk_users_parent_id", "users", "parents", ["parent_id"], ["id"])
    op.create_index("ix_users_parent_id", "users", ["parent_id"])
    op.create_check_constraint("ck_users_identity", "users", IDENTITY_CHECK)
    op.create_check_constraint("ck_users_login_parent", "users", LOGIN_PARENT_CHECK)

    # --- consent records, e-mailed links, login failures -------------------
    op.create_table(
        "consents",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.String(255),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(8), nullable=False),
        sa.Column(
            "parent_id",
            sa.String(32),
            sa.ForeignKey("parents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("terms_version", sa.String(32), nullable=False),
        sa.Column("given_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_consents_user_id", "consents", ["user_id"])

    op.create_table(
        "email_tokens",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("purpose", sa.String(16), nullable=False),
        sa.Column(
            "user_id",
            sa.String(255),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "parent_id",
            sa.String(32),
            sa.ForeignKey("parents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("token_hash", name="uq_email_tokens_token_hash"),
    )
    op.create_index("ix_email_tokens_user_id", "email_tokens", ["user_id"])
    op.create_index("ix_email_tokens_parent_id", "email_tokens", ["parent_id"])
    op.create_index("ix_email_tokens_created_at", "email_tokens", ["created_at"])
    op.create_index("ix_email_tokens_expires_at", "email_tokens", ["expires_at"])

    op.create_table(
        "login_failures",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("login", sa.String(64), nullable=False),
        sa.Column("ip_hash", sa.String(64), nullable=False),
        sa.Column("at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_login_failures_login", "login_failures", ["login"])
    op.create_index("ix_login_failures_ip_hash", "login_failures", ["ip_hash"])
    op.create_index("ix_login_failures_at", "login_failures", ["at"])


def downgrade() -> None:
    # Login accounts cannot exist in the old schema (no Google id, no e-mail)
    bind = op.get_bind()
    count = bind.execute(sa.text("SELECT count(*) FROM users WHERE google_sub IS NULL")).scalar()
    if count:
        raise RuntimeError(
            f"{count} login/password accounts exist; erase them before downgrading below 010"
        )

    op.drop_table("login_failures")
    op.drop_table("email_tokens")
    op.drop_table("consents")

    op.drop_constraint("ck_users_login_parent", "users", type_="check")
    op.drop_constraint("ck_users_identity", "users", type_="check")
    op.drop_index("ix_users_parent_id", table_name="users")
    op.drop_constraint("fk_users_parent_id", "users", type_="foreignkey")
    op.drop_constraint("uq_users_login", "users", type_="unique")
    for column in (
        "session_version",
        "parent_id",
        "pending_since",
        "status",
        "birth_year",
        "password_hash",
        "login",
    ):
        op.drop_column("users", column)
    op.drop_table("parents")

    op.alter_column("users", "email", existing_type=sa.String(255), nullable=False)
    op.drop_constraint("uq_users_google_sub", "users", type_="unique")
    op.drop_column("users", "google_sub")
    op.alter_column("users", "id", new_column_name="google_sub")
