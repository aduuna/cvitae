import uuid
from typing import Self

from fastapi import APIRouter, status
from pydantic import BaseModel, model_validator

from api.ai.models import AiModel
from api.deps import (
    AiRuns,
    AppSettings,
    CurrentUser,
    Documents,
    Jobs,
    Profiles,
    Providers,
    Renderer,
    Versions,
)
from api.errors import AI_ERROR_RESPONSES
from api.ports.llm.base import ProviderName
from api.routers.documents import Document
from api.routers.jobs import JobCreate, JobSummary
from api.services import tailoring as service
from api.services.ai_models import choose_model
from cvcore.factguard import FactIssue
from cvcore.render import PlaceholderRef

router = APIRouter(prefix="/tailor", tags=["tailor"], responses=AI_ERROR_RESPONSES)


class TailorRequest(BaseModel):
    profile_id: uuid.UUID
    job_id: uuid.UUID | None = None
    """A saved job; or give `job` to save a new one."""
    job: JobCreate | None = None
    template_id: str | None = None
    """Defaults to the user's default template, else classic."""
    ai_model: AiModel | None = None
    """Defaults to the user's chosen model."""

    @model_validator(mode="after")
    def _one_job(self) -> Self:
        if (self.job_id is None) == (self.job is None):
            raise ValueError("give job_id or job, not both")
        return self


class BulletDiff(BaseModel):
    source_id: str
    entry: str
    source_text: str
    text: str
    rationale: str | None


class DroppedBullet(BaseModel):
    source_id: str
    entry: str
    text: str


class TailorResult(BaseModel):
    document: Document
    job: JobSummary
    ai_model: AiModel
    provider: ProviderName
    model: str
    """The provider's model id that answered."""
    issues: list[FactIssue]
    """What the fact guard corrected."""
    changes: list[BulletDiff]
    dropped: list[DroppedBullet]
    placeholders: list[PlaceholderRef]
    missing_keywords: list[str]
    """Job keywords the profile does not cover. Only add them if they are true."""


@router.post("", status_code=status.HTTP_201_CREATED)
async def tailor(
    body: TailorRequest,
    user: CurrentUser,
    providers: Providers,
    settings: AppSettings,
    runs: AiRuns,
    profiles: Profiles,
    jobs: Jobs,
    documents: Documents,
    versions: Versions,
    renderer: Renderer,
) -> TailorResult:
    """Create a tailored CV. Regenerating from the review screen deletes the draft CV first."""
    # The model also analyses the job; job analysis uses the provider's small model.
    new_job = None
    if body.job is not None:
        new_job = service.NewJob(
            description=body.job.description,
            title=body.job.title,
            company=body.job.company,
            url=str(body.job.url) if body.job.url else None,
        )
    choice = choose_model(
        providers,
        user,
        body.ai_model,
        default=settings.default_ai_model,
        enforce_plans=settings.enforce_ai_plans,
    )
    result = await service.tailor(
        choice,
        runs,
        profiles,
        jobs,
        documents,
        versions,
        renderer,
        profile_id=body.profile_id,
        job_id=body.job_id,
        new_job=new_job,
        template_id=body.template_id or user.default_template_id,
    )
    return TailorResult(
        document=Document.model_validate(result.document),
        job=JobSummary.model_validate(result.job),
        ai_model=result.choice.option.id,
        provider=result.choice.option.provider,
        model=result.model,
        issues=result.issues,
        changes=[
            BulletDiff.model_validate(change, from_attributes=True) for change in result.changes
        ],
        dropped=[DroppedBullet.model_validate(d, from_attributes=True) for d in result.dropped],
        placeholders=result.placeholders,
        missing_keywords=result.missing_keywords,
    )
