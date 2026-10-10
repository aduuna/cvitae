"""Users choose an AI model instead of a provider; MiMo joins Claude and Gemini.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # No check constraint on the model: the list of models changes without migrations.
    op.add_column("users", sa.Column("preferred_ai_model", sa.String(32), nullable=True))
    op.drop_constraint("ck_users_preferred_provider", "users", type_="check")
    op.drop_column("users", "preferred_provider")

    op.drop_constraint("ck_ai_runs_provider", "ai_runs", type_="check")
    op.create_check_constraint(
        "ck_ai_runs_provider", "ai_runs", "provider IN ('claude', 'gemini', 'mimo')"
    )


def downgrade() -> None:
    op.execute("DELETE FROM ai_runs WHERE provider = 'mimo'")
    op.drop_constraint("ck_ai_runs_provider", "ai_runs", type_="check")
    op.create_check_constraint("ck_ai_runs_provider", "ai_runs", "provider IN ('claude', 'gemini')")

    op.add_column(
        "users",
        sa.Column("preferred_provider", sa.String(16), server_default="claude", nullable=False),
    )
    op.create_check_constraint(
        "ck_users_preferred_provider", "users", "preferred_provider IN ('claude', 'gemini')"
    )
    op.drop_column("users", "preferred_ai_model")
