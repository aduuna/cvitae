"""Version history of a CV: explicit saves, restores and the snapshots that make restores safe."""

import uuid
from collections.abc import Sequence

from api.db.models import Document, DocumentVersion
from api.errors import NotFound
from api.repositories.documents import DocumentRepository, DocumentVersionRepository
from api.services.documents import get_document


async def list_versions(
    documents: DocumentRepository, versions: DocumentVersionRepository, document_id: uuid.UUID
) -> Sequence[DocumentVersion]:
    document = await get_document(documents, document_id)
    return await versions.list_for(document.id)


async def save_version(
    documents: DocumentRepository, versions: DocumentVersionRepository, document_id: uuid.UUID
) -> DocumentVersion:
    """The user's explicit "Save version"."""
    document = await get_document(documents, document_id)
    return await _snapshot(versions, document, "manual")


async def restore_version(
    documents: DocumentRepository,
    versions: DocumentVersionRepository,
    document_id: uuid.UUID,
    number: int,
) -> Document:
    """Make version `number` the current content. Unsaved current content is kept as an
    autosave version first, so a restore can itself be undone."""
    document = await get_document(documents, document_id)
    version = await versions.get_number(document.id, number)
    if version is None:
        raise NotFound(f"Version {number} of this CV does not exist.")
    latest = await versions.latest(document.id)
    if latest is None or (latest.content, latest.source_files) != (
        document.content,
        document.source_files,
    ):
        await _snapshot(versions, document, "autosave")
    document = await documents.update(
        document, content=dict(version.content), source_files=version.source_files
    )
    await _snapshot(versions, document, "restore")
    return document


async def _snapshot(
    versions: DocumentVersionRepository, document: Document, reason: str
) -> DocumentVersion:
    return await versions.create(
        document_id=document.id,
        reason=reason,
        content=dict(document.content),
        source_files=document.source_files,
    )
