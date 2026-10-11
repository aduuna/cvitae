"""Documents (CVs): snapshots of a profile with a template and a name."""

import uuid
from collections.abc import Sequence

from api.billing.plans import Plan
from api.db.models import Document
from api.errors import Conflict, NotFound
from api.ports.renderer import RendererClient
from api.repositories.documents import DocumentRepository
from api.repositories.profiles import ProfileRepository
from api.services.profiles import get_profile
from api.services.quotas import require_room
from api.services.templates import DEFAULT_TEMPLATE_ID, require_template
from cvcore.models import CvContent


async def list_documents(documents: DocumentRepository) -> Sequence[Document]:
    return await documents.list_recent()


async def get_document(documents: DocumentRepository, document_id: uuid.UUID) -> Document:
    document = await documents.get(document_id)
    if document is None:
        raise NotFound("This CV does not exist or was deleted.")
    return document


async def create_document(
    documents: DocumentRepository,
    profiles: ProfileRepository,
    renderer: RendererClient,
    *,
    profile_id: uuid.UUID,
    name: str | None = None,
    template_id: str | None = None,
    plan: Plan,
) -> Document:
    """A new CV holding a copy of the profile's content; later profile edits do not change it."""
    profile = await get_profile(profiles, profile_id)
    template = await require_template(renderer, template_id or DEFAULT_TEMPLATE_ID)
    await require_room("documents", plan, documents)
    return await documents.create(
        profile_id=profile.id,
        name=name or f"{profile.name} CV",
        template_id=template.id,
        content=dict(profile.content),
    )


async def update_document(
    documents: DocumentRepository,
    renderer: RendererClient,
    document_id: uuid.UUID,
    *,
    name: str | None = None,
    template_id: str | None = None,
    content: CvContent | None = None,
) -> Document:
    document = await get_document(documents, document_id)
    if document.mode == "ejected" and (template_id is not None or content is not None):
        raise Conflict("This CV is edited as Typst, so its form content and template are fixed.")
    values: dict[str, object] = {}
    if name is not None:
        values["name"] = name
    if template_id is not None:
        values["template_id"] = (await require_template(renderer, template_id)).id
    if content is not None:
        values["content"] = content.model_dump(mode="json")
    return await documents.update(document, **values)


async def duplicate_document(
    documents: DocumentRepository, document_id: uuid.UUID, *, plan: Plan
) -> Document:
    source = await get_document(documents, document_id)
    await require_room("documents", plan, documents)
    return await documents.create(
        profile_id=source.profile_id,
        job_id=source.job_id,
        name=f"{source.name} (copy)",
        template_id=source.template_id,
        mode=source.mode,
        content=dict(source.content),
        source_files=dict(source.source_files) if source.source_files else None,
        page_count=source.page_count,
    )


async def delete_document(documents: DocumentRepository, document_id: uuid.UUID) -> None:
    if not await documents.delete(document_id):
        raise NotFound("This CV does not exist or was deleted.")
