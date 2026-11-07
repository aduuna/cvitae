"""The browser extension. Connections are managed from the web app (Firebase session); the other
routes are called by the extension with its own token (`Authorization: Bearer cvx_...`)."""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Response, status
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from api.ai.models import AiModel
from api.ai.prompts.draft_answers import JobAd, Question
from api.deps import (
    AppSettings,
    ExtensionAiRuns,
    ExtensionConnection,
    ExtensionDocuments,
    ExtensionJobs,
    ExtensionPlan,
    ExtensionProfiles,
    ExtensionTokens,
    OwnExtensionTokens,
    Providers,
    Renderer,
)
from api.errors import AI_ERROR_RESPONSES, ERROR_RESPONSES, ErrorEnvelope
from api.routers.jobs import MAX_DESCRIPTION, JobCreate, JobSummary
from api.services import answers
from api.services import extension as service
from api.services.ai_models import choose_model
from cvcore.answers import FinishedAnswer
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


class AnswerSource(BaseModel):
    kind: Literal["profile", "document"]
    id: uuid.UUID


class AnswerJob(BaseModel):
    """A job ad read from the page; not saved."""

    description: str = Field(min_length=1, max_length=MAX_DESCRIPTION)
    title: str = Field("", max_length=200)
    company: str = Field("", max_length=200)


class AnswerQuestion(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    """The field's id in the extension's scan of the page."""
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
    """The question as the form asks it: its label and help text."""
    multiline: bool = True
    """False for a single-line field."""
    max_words: int | None = Field(None, ge=1, le=2000)
    max_chars: int | None = Field(None, ge=1, le=20_000)
    previous: str | None = Field(None, max_length=5000)
    """The draft to replace, for Redraft."""


class AnswersRequest(BaseModel):
    source: AnswerSource
    """The profile or CV to draft from."""
    job_id: uuid.UUID | None = None
    """A saved job; it wins over `job`."""
    job: AnswerJob | None = None
    questions: list[AnswerQuestion] = Field(min_length=1, max_length=20)
    ai_model: AiModel | None = None
    """Defaults to the user's chosen model."""

    @field_validator("questions")
    @classmethod
    def unique_ids(cls, questions: list[AnswerQuestion]) -> list[AnswerQuestion]:
        if len({question.id for question in questions}) != len(questions):
            raise ValueError("each question needs its own id")
        return questions


class AnswersResult(BaseModel):
    answers: list[FinishedAnswer]
    """One per question, in the order asked. Nothing is saved."""
    ai_model: AiModel
    ai_model_label: str
    """How the panel names the model: "Drafted with Claude Haiku"."""
    model: str
    """The provider's model id that answered."""


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


@router.post("/answers", responses=AI_ERROR_RESPONSES)
async def draft_answers(
    body: AnswersRequest,
    connection: ExtensionConnection,
    plan: ExtensionPlan,
    providers: Providers,
    settings: AppSettings,
    runs: ExtensionAiRuns,
    profiles: ExtensionProfiles,
    documents: ExtensionDocuments,
    jobs: ExtensionJobs,
) -> AnswersResult:
    """Drafted answers to a form's open questions, from a profile or CV and the job ad. Takes one
    AI run, however many questions; saves nothing."""
    choice = choose_model(
        providers,
        connection.user,
        body.ai_model,
        default=settings.default_ai_model,
        enforce_plans=settings.enforce_ai_plans,
        plan=plan,
    )
    result = await answers.draft_answers(
        choice,
        runs,
        profiles,
        documents,
        jobs,
        source=answers.Source(kind=body.source.kind, id=body.source.id),
        questions=[
            Question(
                id=question.id,
                text=question.text,
                single_line=not question.multiline,
                max_words=question.max_words,
                max_chars=question.max_chars,
                previous=question.previous,
            )
            for question in body.questions
        ],
        job_id=body.job_id,
        job=JobAd(description=body.job.description, title=body.job.title, company=body.job.company)
        if body.job
        else None,
        plan=plan,
    )
    return AnswersResult(
        answers=result.answers,
        ai_model=result.choice.option.id,
        ai_model_label=result.choice.option.label,
        model=result.model,
    )
