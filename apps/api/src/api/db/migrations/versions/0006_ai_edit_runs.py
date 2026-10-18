"""AI runs can be edits: a change asked for in the editor's AI panel.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-17
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_ai_runs_task", "ai_runs", type_="check")
    op.create_check_constraint(
        "ck_ai_runs_task", "ai_runs", "task IN ('import', 'analyze_job', 'tailor', 'edit')"
    )


def downgrade() -> None:
    op.execute("DELETE FROM ai_runs WHERE task = 'edit'")
    op.drop_constraint("ck_ai_runs_task", "ai_runs", type_="check")
    op.create_check_constraint(
        "ck_ai_runs_task", "ai_runs", "task IN ('import', 'analyze_job', 'tailor')"
    )
