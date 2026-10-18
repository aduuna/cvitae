"""ORM tables. Content columns hold CvContent as JSON; see cvcore.models."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    false,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from api.db.base import Entity, utcnow


class User(Entity):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("plan IN ('free', 'pro')", name="plan"),)

    firebase_uid: Mapped[str] = mapped_column(String(128), unique=True)
    email: Mapped[str] = mapped_column(String(320))
    display_name: Mapped[str | None] = mapped_column(String(200))
    preferred_ai_model: Mapped[str | None] = mapped_column(String(32))
    """An api.ai.models.AiModel; None means the server's default."""
    plan: Mapped[str] = mapped_column(String(16), default="free", server_default="free")
    default_template_id: Mapped[str | None] = mapped_column(String(64))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UserOwned(Entity):
    __abstract__ = True

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))


class Profile(UserOwned):
    __tablename__ = "profiles"
    __table_args__ = (
        Index("ix_profiles_user_id_updated_at", "user_id", text("updated_at DESC")),
        Index(
            "uq_profiles_user_id_default",
            "user_id",
            unique=True,
            postgresql_where=text("is_default"),
        ),
    )

    name: Mapped[str] = mapped_column(String(200))
    is_default: Mapped[bool] = mapped_column(default=False, server_default=false())
    content: Mapped[dict[str, Any]] = mapped_column(JSONB)


class Job(UserOwned):
    """A saved job description. The description is user content: never logged."""

    __tablename__ = "jobs"
    __table_args__ = (Index("ix_jobs_user_id_updated_at", "user_id", text("updated_at DESC")),)

    title: Mapped[str] = mapped_column(String(200))
    company: Mapped[str] = mapped_column(String(200))
    url: Mapped[str | None] = mapped_column(String(2048))
    description: Mapped[str] = mapped_column(Text)
    analysis: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    """JobAnalysis, once the job has been analysed."""


class Document(UserOwned):
    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_documents_user_id_updated_at", "user_id", text("updated_at DESC")),
        CheckConstraint("mode IN ('structured', 'ejected')", name="mode"),
    )

    # A CV is a snapshot: deleting its profile keeps the CV.
    profile_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("profiles.id", ondelete="SET NULL")
    )
    # The job a tailored CV was made for. Deleting the job keeps the CV.
    job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(200))
    template_id: Mapped[str] = mapped_column(String(64))
    mode: Mapped[str] = mapped_column(String(16), default="structured", server_default="structured")
    content: Mapped[dict[str, Any]] = mapped_column(JSONB)
    source_files: Mapped[dict[str, str] | None] = mapped_column(JSONB)
    page_count: Mapped[int | None] = mapped_column()


class DocumentVersion(Entity):
    __tablename__ = "document_versions"
    __table_args__ = (
        UniqueConstraint("document_id", "number"),
        CheckConstraint("reason IN ('tailor', 'manual', 'restore', 'autosave')", name="reason"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    number: Mapped[int] = mapped_column()
    reason: Mapped[str] = mapped_column(String(16))
    content: Mapped[dict[str, Any]] = mapped_column(JSONB)
    source_files: Mapped[dict[str, str] | None] = mapped_column(JSONB)


class Upload(UserOwned):
    """A file the user uploaded (a CV to import). The bytes live in storage under storage_key."""

    __tablename__ = "uploads"
    __table_args__ = (Index("ix_uploads_user_id_created_at", "user_id", text("created_at DESC")),)

    storage_key: Mapped[str] = mapped_column(String(512), unique=True)
    filename: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(128))
    size_bytes: Mapped[int] = mapped_column()


class AiRun(UserOwned):
    """One AI call, successful or not. No prompt or output content: it drives quotas and cost."""

    __tablename__ = "ai_runs"
    __table_args__ = (
        Index("ix_ai_runs_user_id_created_at", "user_id", text("created_at DESC")),
        CheckConstraint("task IN ('import', 'analyze_job', 'tailor', 'edit')", name="task"),
        CheckConstraint("provider IN ('claude', 'gemini', 'mimo')", name="provider"),
        CheckConstraint("status IN ('succeeded', 'failed')", name="status"),
    )

    task: Mapped[str] = mapped_column(String(16))
    provider: Mapped[str] = mapped_column(String(16))
    model: Mapped[str] = mapped_column(String(64))
    prompt_version: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16))
    error_code: Mapped[str | None] = mapped_column(String(64))
    input_tokens: Mapped[int] = mapped_column(default=0, server_default="0")
    output_tokens: Mapped[int] = mapped_column(default=0, server_default="0")
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    duration_ms: Mapped[int] = mapped_column(default=0, server_default="0")


class Subscription(UserOwned):
    """The user's Paystack subscription, mirrored from Paystack's events. One per user."""

    __tablename__ = "subscriptions"
    __table_args__ = (
        UniqueConstraint("user_id"),
        Index("ix_subscriptions_paystack_subscription_code", "paystack_subscription_code"),
        Index("ix_subscriptions_paystack_customer_code", "paystack_customer_code"),
        CheckConstraint(
            "status IN ('active', 'non_renewing', 'attention', 'cancelled')", name="status"
        ),
    )

    paystack_customer_code: Mapped[str] = mapped_column(String(64))
    paystack_subscription_code: Mapped[str | None] = mapped_column(String(64))
    """Known once Paystack sends subscription.create."""
    plan_code: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16))
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    """Paid up to here: the next payment date Paystack last reported."""


class WebhookEvent(Entity):
    """A webhook already processed, so a repeated delivery changes nothing. Not user content."""

    __tablename__ = "webhook_events"

    provider: Mapped[str] = mapped_column(String(16))
    event_key: Mapped[str] = mapped_column(String(255), unique=True)
    event_type: Mapped[str] = mapped_column(String(64))
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
