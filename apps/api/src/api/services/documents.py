"""Documents (CVs): snapshots of a profile with a template and a name, and maybe a custom layout."""

import uuid
from collections.abc import Sequence

from api.billing.plans import Plan
from api.db.models import Document
from api.errors import NotFound
from api.repositories.documents import DocumentRepository
from api.repositories.jobs import JobRepository
from api.repositories.profiles import ProfileRepository
from api.services.jobs import get_job
from api.services.profiles import get_profile
from api.services.quotas import require_room
from api.services.templates import DEFAULT_TEMPLATE_ID, TemplateCatalog
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
    catalog: TemplateCatalog,
    *,
    profile_id: uuid.UUID,
    name: str | None = None,
    template_id: str | None = None,
    plan: Plan,
) -> Document:
    """A new CV holding a copy of the profile's content; later profile edits do not change it."""
    profile = await get_profile(profiles, profile_id)
    template = await catalog.require(template_id or DEFAULT_TEMPLATE_ID)
    await require_room("documents", plan, documents)
    return await documents.create(
        profile_id=profile.id,
        name=name or f"{profile.name} CV",
        template_id=template.id,
        content=dict(profile.content),
    )


async def update_document(
    documents: DocumentRepository,
    catalog: TemplateCatalog,
    jobs: JobRepository,
    document_id: uuid.UUID,
    *,
    name: str | None = None,
    template_id: str | None = None,
    content: CvContent | None = None,
    job_id: uuid.UUID | None = None,
    layout: str | None = None,
    reset_layout: bool = False,
) -> Document:
    """`job_id` links a saved job: the ATS score checks the CV against it, the PDF is named for
    its company and the browser extension offers the CV on its pages. `layout` sets the CV's
    custom main.typ and `reset_layout` removes it; switching to another template removes it too,
    unless the same update sets one."""
    document = await get_document(documents, document_id)
    values: dict[str, object] = {}
    if name is not None:
        values["name"] = name
    if template_id is not None:
        values["template_id"] = (await catalog.require(template_id)).id
        if values["template_id"] != document.template_id:
            values["layout"] = None
    if content is not None:
        values["content"] = content.model_dump(mode="json")
    if reset_layout:
        values["layout"] = None
    if layout is not None:
        values["layout"] = layout
    if job_id is not None:
        values["job_id"] = (await get_job(jobs, job_id)).id
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
        content=dict(source.content),
        layout=source.layout,
        page_count=source.page_count,
    )


async def delete_document(documents: DocumentRepository, document_id: uuid.UUID) -> None:
    if not await documents.delete(document_id):
        raise NotFound("This CV does not exist or was deleted.")
