"""ORM tables. Content columns hold CvContent as JSON; see cvcore.models."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    false,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from api.db.base import Entity


class User(Entity):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("preferred_provider IN ('claude', 'gemini')", name="preferred_provider"),
        CheckConstraint("plan IN ('free', 'pro')", name="plan"),
    )

    firebase_uid: Mapped[str] = mapped_column(String(128), unique=True)
    email: Mapped[str] = mapped_column(String(320))
    display_name: Mapped[str | None] = mapped_column(String(200))
    preferred_provider: Mapped[str] = mapped_column(
        String(16), default="claude", server_default="claude"
    )
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
    # The foreign key to jobs arrives with the jobs table (M3).
    job_id: Mapped[uuid.UUID | None] = mapped_column()
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
