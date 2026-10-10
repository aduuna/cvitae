"""Jobs, AI runs, and the link from documents to jobs.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-10
"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _owned(table: str) -> list[sa.Column[Any] | sa.Constraint]:
    return [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=f"pk_{table}"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=f"fk_{table}_user_id_users", ondelete="CASCADE"
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "jobs",
        *_owned("jobs"),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("company", sa.String(200), nullable=False),
        sa.Column("url", sa.String(2048), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("analysis", postgresql.JSONB(), nullable=True),
    )
    op.create_index("ix_jobs_user_id_updated_at", "jobs", ["user_id", sa.text("updated_at DESC")])

    op.create_table(
        "ai_runs",
        *_owned("ai_runs"),
        sa.Column("task", sa.String(16), nullable=False),
        sa.Column("provider", sa.String(16), nullable=False),
        sa.Column("model", sa.String(64), nullable=False),
        sa.Column("prompt_version", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("input_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("output_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("cost_usd", sa.Numeric(10, 6), nullable=True),
        sa.Column("duration_ms", sa.Integer(), server_default="0", nullable=False),
        sa.CheckConstraint("task IN ('import', 'analyze_job', 'tailor')", name="ck_ai_runs_task"),
        sa.CheckConstraint("provider IN ('claude', 'gemini')", name="ck_ai_runs_provider"),
        sa.CheckConstraint("status IN ('succeeded', 'failed')", name="ck_ai_runs_status"),
    )
    op.create_index(
        "ix_ai_runs_user_id_created_at", "ai_runs", ["user_id", sa.text("created_at DESC")]
    )

    # Rows from before jobs existed may point nowhere; clear them so the constraint holds.
    op.execute("UPDATE documents SET job_id = NULL WHERE job_id IS NOT NULL")
    op.create_foreign_key(
        "fk_documents_job_id_jobs", "documents", "jobs", ["job_id"], ["id"], ondelete="SET NULL"
    )


def downgrade() -> None:
    op.drop_constraint("fk_documents_job_id_jobs", "documents", type_="foreignkey")
    op.drop_table("ai_runs")
    op.drop_table("jobs")
