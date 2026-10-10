"""Saved job descriptions and their analysis. Descriptions are user content: never logged."""

import uuid
from collections.abc import Sequence

from api.ai import tasks
from api.db.models import Job
from api.errors import NotFound
from api.repositories.ai_runs import AiRunRepository
from api.repositories.jobs import JobRepository
from api.services.ai_models import ModelChoice
from cvcore.ai import JobAnalysis


async def list_jobs(jobs: JobRepository) -> Sequence[Job]:
    return await jobs.list_recent()


async def get_job(jobs: JobRepository, job_id: uuid.UUID) -> Job:
    job = await jobs.get(job_id)
    if job is None:
        raise NotFound("This job does not exist or was deleted.")
    return job


async def create_job(
    jobs: JobRepository,
    *,
    description: str,
    title: str = "",
    company: str = "",
    url: str | None = None,
) -> Job:
    return await jobs.create(
        title=title.strip(), company=company.strip(), url=url, description=description.strip()
    )


async def delete_job(jobs: JobRepository, job_id: uuid.UUID) -> None:
    """Deleting a job keeps the CVs made for it; they just lose the link."""
    await jobs.delete((await get_job(jobs, job_id)).id)


async def ensure_analysis(
    jobs: JobRepository, job: Job, choice: ModelChoice, runs: AiRunRepository
) -> JobAnalysis:
    """The job's analysis, made once and kept. Fills in a title or company the user left out."""
    if job.analysis is not None:
        return JobAnalysis.model_validate(job.analysis)
    result = await tasks.analyze_job(
        choice, runs, description=job.description, title=job.title, company=job.company
    )
    analysis = result.output
    await jobs.update(
        job,
        analysis=analysis.model_dump(mode="json"),
        title=job.title or analysis.title[:200],
        company=job.company or analysis.company[:200],
    )
    return analysis
