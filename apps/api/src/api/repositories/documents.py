import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import ColumnElement, func, select

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
