"""Version snapshots of a CV: its content and custom layout, kept as one version."""

from api.db.models import Document, DocumentVersion
from api.repositories.documents import DocumentVersionRepository


async def snapshot(
    versions: DocumentVersionRepository, document: Document, reason: str
) -> DocumentVersion:
    """Keep the CV as it is now, content and layout together, as a version."""
    return await versions.create(
        document_id=document.id,
        reason=reason,
        content=dict(document.content),
        layout=document.layout,
    )


async def keep_current_work(versions: DocumentVersionRepository, document: Document) -> None:
    """Keep the CV as an autosave version before something replaces it, unless its latest version
    already holds the same content and layout. That is what lets a restore undo the change."""
    latest = await versions.latest(document.id)
    if latest is None or (latest.content, latest.layout) != (document.content, document.layout):
        await snapshot(versions, document, "autosave")
