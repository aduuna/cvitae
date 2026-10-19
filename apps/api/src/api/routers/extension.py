"""The browser extension. Connections are managed from the web app (Firebase session); the other
routes are called by the extension with its own token (`Authorization: Bearer cvx_...`)."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Response, status
from pydantic import BaseModel, ConfigDict, Field

from api.deps import (
    ExtensionConnection,
    ExtensionDocuments,
    ExtensionJobs,
    ExtensionProfiles,
    ExtensionTokens,
    OwnExtensionTokens,
    Renderer,
)
from api.errors import ERROR_RESPONSES, ErrorEnvelope
from api.routers.jobs import JobCreate, JobSummary
from api.services import extension as service
from cvcore.application import ApplicationData

router = APIRouter(prefix="/extension", tags=["extension"], responses=ERROR_RESPONSES)


class ExtensionConnectionInfo(BaseModel):
    """A browser the extension is connected in."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    label: str
    created_at: datetime
    last_used_at: datetime | None
    """Updated at most once an hour."""


class ExtensionConnectionCreate(BaseModel):
    label: str = Field("", max_length=100)
    """Where it is connected, for example "Chrome on macOS"."""


class ExtensionConnectionCreated(ExtensionConnectionInfo):
    token: str
    """Shown this once. The web app hands it to the extension and keeps no copy."""


class SourceProfile(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    is_default: bool
    updated_at: datetime


class SourceDocument(BaseModel):
    id: uuid.UUID
    name: str
    job_id: uuid.UUID | None
    placeholders: int
    """A CV with placeholders cannot be attached as a PDF until they are filled."""
    updated_at: datetime


class ExtensionSession(BaseModel):
    email: str
    display_name: str | None
    profiles: list[SourceProfile]
    documents: list[SourceDocument]
    """Form-mode CVs, newest first."""
    jobs: list[JobSummary]
    """Saved jobs, so the extension can match the page it is on to the CV made for it."""


class SavedJob(BaseModel):
    job: JobSummary
    created: bool
    """False when this ad (same URL) was saved before; the earlier job is returned unchanged."""


# Managed from the web app, signed in as usual.


@router.get("/connections")
async def list_connections(tokens: ExtensionTokens) -> list[ExtensionConnectionInfo]:
    rows = await service.list_connections(tokens)
    return [ExtensionConnectionInfo.model_validate(row) for row in rows]


@router.post("/connections", status_code=status.HTTP_201_CREATED)
async def create_connection(
    body: ExtensionConnectionCreate, tokens: ExtensionTokens
) -> ExtensionConnectionCreated:
    row, token = await service.connect(tokens, body.label)
    return ExtensionConnectionCreated(
        id=row.id,
        label=row.label,
        created_at=row.created_at,
        last_used_at=row.last_used_at,
        token=token,
    )


@router.delete("/connections/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connection(connection_id: uuid.UUID, tokens: ExtensionTokens) -> None:
    await service.disconnect(tokens, connection_id)


# Called by the extension with its token.


@router.get("/session")
async def get_session(
    connection: ExtensionConnection,
    profiles: ExtensionProfiles,
    documents: ExtensionDocuments,
    jobs: ExtensionJobs,
) -> ExtensionSession:
    sources = await service.list_sources(profiles, documents, jobs)
    return ExtensionSession(
        email=connection.user.email,
        display_name=connection.user.display_name,
        profiles=[SourceProfile.model_validate(row) for row in sources.profiles],
        documents=[
            SourceDocument(
                id=cv.document.id,
                name=cv.document.name,
                job_id=cv.document.job_id,
                placeholders=cv.placeholders,
                updated_at=cv.document.updated_at,
            )
            for cv in sources.documents
        ],
        jobs=[JobSummary.model_validate(row) for row in sources.jobs],
    )


@router.delete("/session", status_code=status.HTTP_204_NO_CONTENT)
async def end_session(connection: ExtensionConnection, tokens: OwnExtensionTokens) -> None:
    """Disconnect this browser: its token stops working."""
    await service.disconnect(tokens, connection.token.id)


@router.get("/profiles/{profile_id}/application")
async def profile_application(
    profile_id: uuid.UUID, profiles: ExtensionProfiles
) -> ApplicationData:
    return await service.profile_application(profiles, profile_id)


@router.get("/documents/{document_id}/application")
async def document_application(
    document_id: uuid.UUID, documents: ExtensionDocuments
) -> ApplicationData:
    return await service.document_application(documents, document_id)


@router.get(
    "/documents/{document_id}/cv.pdf",
    response_class=Response,
    responses={
        200: {"content": {"application/pdf": {}}, "description": "The CV as a PDF"},
        409: {"model": ErrorEnvelope, "description": "Placeholders remain; `details` lists them"},
        503: {"model": ErrorEnvelope},
    },
)
async def document_pdf(
    document_id: uuid.UUID, documents: ExtensionDocuments, jobs: ExtensionJobs, renderer: Renderer
) -> Response:
    pdf = await service.document_pdf(documents, jobs, renderer, document_id)
    return Response(
        pdf.content,
        media_type="application/pdf",
        headers={"Content-Disposition": pdf.content_disposition},
    )


@router.post("/jobs", status_code=status.HTTP_201_CREATED)
async def save_job(body: JobCreate, jobs: ExtensionJobs, response: Response) -> SavedJob:
    job, created = await service.save_job(
        jobs,
        description=body.description,
        title=body.title,
        company=body.company,
        url=str(body.url) if body.url else None,
    )
    if not created:
        response.status_code = status.HTTP_200_OK
    return SavedJob(job=JobSummary.model_validate(job), created=created)
