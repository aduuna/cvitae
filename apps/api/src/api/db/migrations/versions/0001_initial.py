"""Users, profiles, documents and document versions.

Revision ID: 0001
Revises:
Create Date: 2026-10-10
"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _entity_columns() -> list[sa.Column[Any]]:
    return [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "users",
        *_entity_columns(),
        sa.Column("firebase_uid", sa.String(128), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=True),
        sa.Column("preferred_provider", sa.String(16), server_default="claude", nullable=False),
        sa.Column("plan", sa.String(16), server_default="free", nullable=False),
        sa.Column("default_template_id", sa.String(64), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("firebase_uid", name="uq_users_firebase_uid"),
        sa.CheckConstraint(
            "preferred_provider IN ('claude', 'gemini')", name="ck_users_preferred_provider"
        ),
        sa.CheckConstraint("plan IN ('free', 'pro')", name="ck_users_plan"),
    )

    op.create_table(
        "profiles",
        *_entity_columns(),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("content", postgresql.JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_profiles"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_profiles_user_id_users", ondelete="CASCADE"
        ),
    )
    op.create_index(
        "ix_profiles_user_id_updated_at", "profiles", ["user_id", sa.text("updated_at DESC")]
    )
    op.create_index(
        "uq_profiles_user_id_default",
        "profiles",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_default"),
    )

    op.create_table(
        "documents",
        *_entity_columns(),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=True),
        sa.Column("job_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("template_id", sa.String(64), nullable=False),
        sa.Column("mode", sa.String(16), server_default="structured", nullable=False),
        sa.Column("content", postgresql.JSONB(), nullable=False),
        sa.Column("source_files", postgresql.JSONB(), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_documents"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_documents_user_id_users", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["profiles.id"],
            name="fk_documents_profile_id_profiles",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint("mode IN ('structured', 'ejected')", name="ck_documents_mode"),
    )
    op.create_index(
        "ix_documents_user_id_updated_at", "documents", ["user_id", sa.text("updated_at DESC")]
    )

    op.create_table(
        "document_versions",
        *_entity_columns(),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(16), nullable=False),
        sa.Column("content", postgresql.JSONB(), nullable=False),
        sa.Column("source_files", postgresql.JSONB(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_document_versions"),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name="fk_document_versions_document_id_documents",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "document_id", "number", name="uq_document_versions_document_id_number"
        ),
        sa.CheckConstraint(
            "reason IN ('tailor', 'manual', 'restore', 'autosave')",
            name="ck_document_versions_reason",
        ),
    )


def downgrade() -> None:
    op.drop_table("document_versions")
    op.drop_table("documents")
    op.drop_table("profiles")
    op.drop_table("users")
