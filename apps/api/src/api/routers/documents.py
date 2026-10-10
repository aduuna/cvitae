import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Response, status
from pydantic import BaseModel, ConfigDict, Field

from api.deps import Documents, Profiles, Renderer, Versions
from api.errors import ERROR_RESPONSES, ErrorEnvelope
from api.services import documents as service
from api.services import rendering, versions
from cvcore.models import CvContent
from cvcore.rendering import SvgPages

router = APIRouter(prefix="/documents", tags=["documents"], responses=ERROR_RESPONSES)


class DocumentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    template_id: str
    mode: Literal["structured", "ejected"]
    page_count: int | None
    profile_id: uuid.UUID | None
    job_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class Document(DocumentSummary):
    content: CvContent


class DocumentCreate(BaseModel):
    profile_id: uuid.UUID
    name: str | None = Field(None, min_length=1, max_length=200)
    """Defaults to "<profile name> CV"."""
    template_id: str | None = None
    """Defaults to classic."""


class DocumentUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    template_id: str | None = None
    content: CvContent | None = None


class Version(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    number: int
    reason: Literal["tailor", "manual", "restore", "autosave"]
    created_at: datetime


@router.get("")
async def list_documents(documents: Documents) -> list[DocumentSummary]:
    rows = await service.list_documents(documents)
    return [DocumentSummary.model_validate(row) for row in rows]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_document(
    body: DocumentCreate, documents: Documents, profiles: Profiles, renderer: Renderer
) -> Document:
    row = await service.create_document(
        documents,
        profiles,
        renderer,
        profile_id=body.profile_id,
        name=body.name,
        template_id=body.template_id,
    )
    return Document.model_validate(row)


@router.get("/{document_id}")
async def get_document(document_id: uuid.UUID, documents: Documents) -> Document:
    return Document.model_validate(await service.get_document(documents, document_id))


@router.patch("/{document_id}", responses={409: {"model": ErrorEnvelope}})
async def update_document(
    document_id: uuid.UUID, body: DocumentUpdate, documents: Documents, renderer: Renderer
) -> Document:
    row = await service.update_document(
        documents,
        renderer,
        document_id,
        name=body.name,
        template_id=body.template_id,
        content=body.content,
    )
    return Document.model_validate(row)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(document_id: uuid.UUID, documents: Documents) -> None:
    await service.delete_document(documents, document_id)


@router.post("/{document_id}/duplicate", status_code=status.HTTP_201_CREATED)
async def duplicate_document(document_id: uuid.UUID, documents: Documents) -> Document:
    return Document.model_validate(await service.duplicate_document(documents, document_id))


@router.post("/{document_id}/preview", responses={503: {"model": ErrorEnvelope}})
async def preview_document(
    document_id: uuid.UUID, documents: Documents, renderer: Renderer
) -> SvgPages:
    """SVG pages of the saved CV, or 422 with Typst diagnostics in `details`."""
    return await rendering.preview(documents, renderer, document_id)


@router.get(
    "/{document_id}/export.pdf",
    response_class=Response,
    responses={
        200: {"content": {"application/pdf": {}}, "description": "The CV as a PDF"},
        409: {"model": ErrorEnvelope, "description": "Placeholders remain; `details` lists them"},
        503: {"model": ErrorEnvelope},
    },
)
async def export_pdf(
    document_id: uuid.UUID, documents: Documents, renderer: Renderer, force: bool = False
) -> Response:
    pdf = await rendering.export_pdf(documents, renderer, document_id, force=force)
    return Response(
        pdf.content,
        media_type="application/pdf",
        headers={"Content-Disposition": pdf.content_disposition},
    )


@router.get("/{document_id}/versions")
async def list_versions(
    document_id: uuid.UUID, documents: Documents, versions_repo: Versions
) -> list[Version]:
    rows = await versions.list_versions(documents, versions_repo, document_id)
    return [Version.model_validate(row) for row in rows]


@router.post("/{document_id}/versions", status_code=status.HTTP_201_CREATED)
async def save_version(
    document_id: uuid.UUID, documents: Documents, versions_repo: Versions
) -> Version:
    row = await versions.save_version(documents, versions_repo, document_id)
    return Version.model_validate(row)


@router.post("/{document_id}/versions/{number}/restore")
async def restore_version(
    document_id: uuid.UUID, number: int, documents: Documents, versions_repo: Versions
) -> Document:
    row = await versions.restore_version(documents, versions_repo, document_id, number)
    return Document.model_validate(row)
