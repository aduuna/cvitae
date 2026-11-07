"""Templates users make from their own CV, and the `template` AI task.

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_templates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(64), nullable=False),
        sa.Column("name", sa.String(60), nullable=False),
        sa.Column("description", sa.String(200), nullable=False),
        sa.Column("main_typ", sa.Text(), nullable=False),
        sa.Column("paper_sizes", postgresql.JSONB(), nullable=False),
        sa.Column("target_pages", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), server_default="draft", nullable=False),
        sa.Column("upload_id", sa.Uuid(), nullable=True),
        sa.Column("prompt_version", sa.String(32), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_user_templates"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_user_templates_user_id_users", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["upload_id"],
            ["uploads.id"],
            name="fk_user_templates_upload_id_uploads",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("slug", name="uq_user_templates_slug"),
        sa.CheckConstraint("status IN ('draft', 'ready')", name="ck_user_templates_status"),
    )
    op.create_index(
        "ix_user_templates_user_id_created_at",
        "user_templates",
        ["user_id", sa.text("created_at DESC")],
    )
    op.drop_constraint("ck_ai_runs_task", "ai_runs", type_="check")
    op.create_check_constraint(
        "ck_ai_runs_task",
        "ai_runs",
        "task IN ('import', 'analyze_job', 'tailor', 'edit', 'answers', 'template')",
    )


def downgrade() -> None:
    op.execute("DELETE FROM ai_runs WHERE task = 'template'")
    op.drop_constraint("ck_ai_runs_task", "ai_runs", type_="check")
    op.create_check_constraint(
        "ck_ai_runs_task",
        "ai_runs",
        "task IN ('import', 'analyze_job', 'tailor', 'edit', 'answers')",
    )
    op.drop_table("user_templates")
