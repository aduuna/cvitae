"""The ATS score of a CV against the job it is linked to (docs/BACKEND.md, ATS score). It is
computed by `cvcore.ats` from the saved CV, the job's analysis and the CV's profile: no AI run and
no render, so it is free on every plan."""

import uuid
from dataclasses import dataclass

from api.db.models import Job
from api.errors import Conflict
from api.ports.renderer import RendererClient
from api.repositories.documents import DocumentRepository
from api.repositories.jobs import JobRepository
from api.repositories.profiles import ProfileRepository
from api.services.documents import get_document
from api.services.templates import require_template
from cvcore import ats
from cvcore.ai import JobAnalysis
from cvcore.models import CvContent


@dataclass(frozen=True)
class DocumentAts:
    job: Job | None
    """The job the CV is linked to."""
    report: ats.AtsReport | None
    """None when the CV has no job, or its job has not been analysed yet."""


def score_cv(
    content: CvContent,
    job: Job,
    analysis: JobAnalysis,
    *,
    profile: CvContent | None,
    pages: int | None = None,
    target_pages: int | None = None,
) -> ats.AtsReport:
    return ats.score(
        content,
        analysis,
        title=job.title,
        description=job.description,
        profile=profile,
        pages=pages,
        target_pages=target_pages,
    )


async def document_ats(
    documents: DocumentRepository,
    jobs: JobRepository,
    profiles: ProfileRepository,
    renderer: RendererClient,
    document_id: uuid.UUID,
) -> DocumentAts:
    document = await get_document(documents, document_id)
    if document.mode == "ejected":
        raise Conflict("The ATS score reads the form, and this CV is edited as Typst.")
    job = await jobs.get(document.job_id) if document.job_id is not None else None
    if job is None or job.analysis is None:
        return DocumentAts(job=job, report=None)
    profile = await profiles.get(document.profile_id) if document.profile_id is not None else None
    template = await require_template(renderer, document.template_id)
    report = score_cv(
        CvContent.model_validate(document.content),
        job,
        JobAnalysis.model_validate(job.analysis),
        profile=CvContent.model_validate(profile.content) if profile is not None else None,
        pages=document.page_count,
        target_pages=template.target_pages,
    )
    return DocumentAts(job=job, report=report)
