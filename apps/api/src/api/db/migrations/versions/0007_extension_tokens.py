"""Browser extensions connected to an account.

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "extension_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_extension_tokens"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_extension_tokens_user_id_users", ondelete="CASCADE"
        ),
        sa.UniqueConstraint("token_hash", name="uq_extension_tokens_token_hash"),
    )
    op.create_index(
        "ix_extension_tokens_user_id_created_at",
        "extension_tokens",
        ["user_id", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_table("extension_tokens")
