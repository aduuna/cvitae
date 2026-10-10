"""Uploads: files a user uploaded, stored in GCS.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "uploads",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("storage_key", sa.String(512), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(128), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_uploads"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_uploads_user_id_users", ondelete="CASCADE"
        ),
        sa.UniqueConstraint("storage_key", name="uq_uploads_storage_key"),
    )
    op.create_index(
        "ix_uploads_user_id_created_at", "uploads", ["user_id", sa.text("created_at DESC")]
    )


def downgrade() -> None:
    op.drop_table("uploads")
