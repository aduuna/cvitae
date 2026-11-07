"""AI runs can be drafted answers: the extension's drafts for application questions.

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-29
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_ai_runs_task", "ai_runs", type_="check")
    op.create_check_constraint(
        "ck_ai_runs_task",
        "ai_runs",
        "task IN ('import', 'analyze_job', 'tailor', 'edit', 'answers')",
    )


def downgrade() -> None:
    op.execute("DELETE FROM ai_runs WHERE task = 'answers'")
    op.drop_constraint("ck_ai_runs_task", "ai_runs", type_="check")
    op.create_check_constraint(
        "ck_ai_runs_task", "ai_runs", "task IN ('import', 'analyze_job', 'tailor', 'edit')"
    )
