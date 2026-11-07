import uuid
from datetime import datetime

from fastapi import APIRouter, status
from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from api.ai.models import AiModel
from api.deps import AiRuns, AppSettings, CurrentUser, Jobs, Providers, UserPlan
from api.errors import AI_ERROR_RESPONSES, ERROR_RESPONSES
from api.services import jobs as service
from api.services.ai_models import choose_model
from cvcore.ai import JobAnalysis

router = APIRouter(prefix="/jobs", tags=["jobs"], responses=ERROR_RESPONSES)

MAX_DESCRIPTION = 30_000


class JobSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    company: str
    url: str | None
    created_at: datetime
    updated_at: datetime


class Job(JobSummary):
    description: str
    analysis: JobAnalysis | None


class JobCreate(BaseModel):
    description: str = Field(min_length=1, max_length=MAX_DESCRIPTION)
    title: str = Field("", max_length=200)
    company: str = Field("", max_length=200)
    url: HttpUrl | None = None


class AnalyzeRequest(BaseModel):
    ai_model: AiModel | None = None
    """Defaults to the user's chosen model; the analysis runs on its small model."""


@router.get("")
async def list_jobs(jobs: Jobs) -> list[JobSummary]:
    return [JobSummary.model_validate(row) for row in await service.list_jobs(jobs)]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_job(body: JobCreate, jobs: Jobs) -> Job:
    row = await service.create_job(
        jobs,
        description=body.description,
        title=body.title,
        company=body.company,
        url=str(body.url) if body.url else None,
    )
    return Job.model_validate(row)


@router.get("/{job_id}")
async def get_job(job_id: uuid.UUID, jobs: Jobs) -> Job:
    return Job.model_validate(await service.get_job(jobs, job_id))


@router.post("/{job_id}/analyze", responses=AI_ERROR_RESPONSES)
async def analyze_job(
    job_id: uuid.UUID,
    body: AnalyzeRequest,
    user: CurrentUser,
    plan: UserPlan,
    providers: Providers,
    settings: AppSettings,
    runs: AiRuns,
    jobs: Jobs,
) -> Job:
    """The job with its analysis. One AI run when it has none yet; none when it has."""
    choice = choose_model(
        providers,
        user,
        body.ai_model,
        default=settings.default_ai_model,
        enforce_plans=settings.enforce_ai_plans,
        plan=plan,
    )
    return Job.model_validate(await service.analyze_job(jobs, runs, choice, job_id, plan=plan))


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(job_id: uuid.UUID, jobs: Jobs) -> None:
    await service.delete_job(jobs, job_id)
