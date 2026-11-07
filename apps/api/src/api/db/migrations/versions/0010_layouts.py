"""Custom layouts replace ejected CVs: `layout` holds a CV's own main.typ, content stays structured.

Only an ejected CV's main.typ is kept on the way up: its data.json is not read, because `content`
already holds the CV's data (eject was never built, so no real CV has any other files).

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-07
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from cvcore.models import CvContent
from cvcore.render import to_render_json

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table in ("documents", "document_versions"):
        op.add_column(table, sa.Column("layout", sa.Text(), nullable=True))
        op.execute(
            f"UPDATE {table} SET layout = source_files->>'main.typ' "  # noqa: S608 - fixed names
            "WHERE source_files ? 'main.typ'"
        )
        op.drop_column(table, "source_files")
    op.drop_constraint("ck_documents_mode", "documents", type_="check")
    op.drop_column("documents", "mode")


def downgrade() -> None:
    """A CV with a layout goes back to an ejected CV: its layout, and its content as the
    `data.json` a layout reads (`to_render_json`, the rich-text span format)."""
    op.add_column(
        "documents",
        sa.Column("mode", sa.String(16), server_default="structured", nullable=False),
    )
    op.create_check_constraint(
        "ck_documents_mode", "documents", "mode IN ('structured', 'ejected')"
    )
    connection = op.get_bind()
    for table in ("documents", "document_versions"):
        op.add_column(table, sa.Column("source_files", postgresql.JSONB(), nullable=True))
        rows = connection.execute(
            sa.text(f"SELECT id, layout, content FROM {table} WHERE layout IS NOT NULL")  # noqa: S608
        ).all()
        for row_id, layout, content in rows:
            data = json.dumps(to_render_json(CvContent.model_validate(content)))
            connection.execute(
                sa.text(f"UPDATE {table} SET source_files = CAST(:files AS jsonb) WHERE id = :id"),  # noqa: S608
                {"files": json.dumps({"main.typ": layout, "data.json": data}), "id": row_id},
            )
        op.drop_column(table, "layout")
    # The layout column is gone, so mark the CVs by the files they now hold.
    op.execute("UPDATE documents SET mode = 'ejected' WHERE source_files IS NOT NULL")
