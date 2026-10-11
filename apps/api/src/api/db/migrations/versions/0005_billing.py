"""Subscriptions mirrored from Paystack, and processed webhook events.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-10
"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column[Any]]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("paystack_customer_code", sa.String(64), nullable=False),
        sa.Column("paystack_subscription_code", sa.String(64), nullable=True),
        sa.Column("plan_code", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_subscriptions"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_subscriptions_user_id_users", ondelete="CASCADE"
        ),
        sa.UniqueConstraint("user_id", name="uq_subscriptions_user_id"),
        sa.CheckConstraint(
            "status IN ('active', 'non_renewing', 'attention', 'cancelled')",
            name="ck_subscriptions_status",
        ),
    )
    op.create_index(
        "ix_subscriptions_paystack_subscription_code",
        "subscriptions",
        ["paystack_subscription_code"],
    )
    op.create_index(
        "ix_subscriptions_paystack_customer_code", "subscriptions", ["paystack_customer_code"]
    )

    op.create_table(
        "webhook_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.Column("provider", sa.String(16), nullable=False),
        sa.Column("event_key", sa.String(255), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_webhook_events"),
        sa.UniqueConstraint("event_key", name="uq_webhook_events_event_key"),
    )


def downgrade() -> None:
    op.drop_table("webhook_events")
    op.drop_table("subscriptions")
