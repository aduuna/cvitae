import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import ColumnElement, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import Document, DocumentVersion
from api.repositories.base import UserScopedRepository


class DocumentRepository(UserScopedRepository[Document]):
    model = Document

    async def list_recent(self) -> Sequence[Document]:
        return await self.list(Document.updated_at.desc())


class DocumentVersionRepository(UserScopedRepository[DocumentVersion]):
    """Versions have no user_id column; they are scoped through their document."""

    model = DocumentVersion

    def _owner(self) -> ColumnElement[bool]:
        owned = select(Document.id).where(Document.user_id == self.user_id)
        return DocumentVersion.document_id.in_(owned.scalar_subquery())

    async def list_for(self, document_id: uuid.UUID) -> Sequence[DocumentVersion]:
        result = await self.session.scalars(
            self._select()
            .where(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.number.desc())
        )
        return result.all()

    async def get_number(self, document_id: uuid.UUID, number: int) -> DocumentVersion | None:
        return await self.session.scalar(
            self._select().where(
                DocumentVersion.document_id == document_id, DocumentVersion.number == number
            )
        )

    async def latest(self, document_id: uuid.UUID) -> DocumentVersion | None:
        versions = await self.session.scalars(
            self._select()
            .where(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.number.desc())
            .limit(1)
        )
        return versions.first()

    async def create(self, **values: Any) -> DocumentVersion:
        """Add the next version of a document the user owns."""
        document_id = values["document_id"]
        owned = await self.session.scalar(
            select(Document.id).where(Document.id == document_id, Document.user_id == self.user_id)
        )
        if owned is None:
            raise LookupError("document not found for this user")
        number = await self.session.scalar(
            select(func.coalesce(func.max(DocumentVersion.number), 0)).where(
                DocumentVersion.document_id == document_id
            )
        )
        row = DocumentVersion(number=(number or 0) + 1, **values)
        self.session.add(row)
        await self.session.flush()
        return row


class VersionPruner:
    """Deletes old autosave versions of every user's CVs, for the scheduled job. Unscoped by
    nature, like the users repository: it is not reachable from a signed-in request, and does
    one thing."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def delete_autosaves_before(self, cutoff: datetime) -> int:
        """Remove the autosave versions created before `cutoff`; how many were removed. Versions
        saved by hand, made by tailoring or by a restore are never touched."""
        result = await self.session.execute(
            delete(DocumentVersion).where(
                DocumentVersion.reason == "autosave", DocumentVersion.created_at < cutoff
            )
        )
        return getattr(result, "rowcount", 0) or 0
