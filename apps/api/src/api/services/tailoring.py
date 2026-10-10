"""Tailoring: a new CV for one job, from a profile, checked by the fact guard."""

import uuid
from collections.abc import Iterator
from dataclasses import dataclass

from api.ai import tasks
from api.db.models import Document, Job
from api.ports.renderer import RendererClient
from api.repositories.ai_runs import AiRunRepository
from api.repositories.documents import DocumentRepository, DocumentVersionRepository
from api.repositories.jobs import JobRepository
from api.repositories.profiles import ProfileRepository
from api.services.ai_models import ModelChoice
from api.services.jobs import create_job, ensure_analysis, get_job
from api.services.profiles import get_profile
from api.services.templates import DEFAULT_TEMPLATE_ID, require_template
from cvcore import factguard
from cvcore.models import Bullet, CvContent
from cvcore.render import PlaceholderRef, find_placeholders
from cvcore.richtext import plain_text


@dataclass(frozen=True)
class NewJob:
    description: str
    title: str = ""
    company: str = ""
    url: str | None = None


@dataclass(frozen=True)
class BulletDiff:
    source_id: str
    entry: str
    """The role, client or project the bullet belongs to, for the Changes panel."""
    source_text: str
    text: str
    rationale: str | None


@dataclass(frozen=True)
class DroppedBullet:
    source_id: str
    entry: str
    text: str


@dataclass(frozen=True)
class TailorResult:
    document: Document
    job: Job
    choice: ModelChoice
    model: str
    """The model id that answered."""
    issues: list[factguard.FactIssue]
    changes: list[BulletDiff]
    dropped: list[DroppedBullet]
    placeholders: list[PlaceholderRef]
    missing_keywords: list[str]


def bullets_with_entries(content: CvContent) -> Iterator[tuple[Bullet, str]]:
    """Every bullet with a label for the entry it belongs to, in reading order."""
    for section in content.sections:
        for item in section.experience:
            label = f"{item.role}, {item.org}"
            yield from ((bullet, label) for bullet in item.bullets)
            for engagement in item.engagements:
                client = f"{engagement.label}: {engagement.name}" if engagement.label else ""
                yield from (
                    (bullet, f"{label} ({client or engagement.name})")
                    for bullet in engagement.bullets
                )
        for project in section.projects:
            yield from ((bullet, project.name) for bullet in project.bullets)
        yield from ((bullet, section.title) for bullet in section.custom)


def compare(
    source: CvContent, tailored: CvContent, rationales: dict[str, str]
) -> tuple[list[BulletDiff], list[DroppedBullet]]:
    originals = {bullet.id: (bullet, entry) for bullet, entry in bullets_with_entries(source)}
    changes, used = [], set()
    for bullet, entry in bullets_with_entries(tailored):
        if bullet.source_id is None or bullet.source_id not in originals:
            continue
        used.add(bullet.source_id)
        original = originals[bullet.source_id][0]
        changes.append(
            BulletDiff(
                source_id=bullet.source_id,
                entry=entry,
                source_text=original.text,
                text=bullet.text,
                rationale=rationales.get(bullet.source_id),
            )
        )
    dropped = [
        DroppedBullet(source_id=bullet_id, entry=entry, text=bullet.text)
        for bullet_id, (bullet, entry) in originals.items()
        if bullet_id not in used and plain_text(bullet.text).strip()
    ]
    return changes, dropped


def document_name(job: Job) -> str:
    title = job.title or "Tailored CV"
    return f"{title} at {job.company}"[:200] if job.company else title[:200]


async def tailor(
    choice: ModelChoice,
    runs: AiRunRepository,
    profiles: ProfileRepository,
    jobs: JobRepository,
    documents: DocumentRepository,
    versions: DocumentVersionRepository,
    renderer: RendererClient,
    *,
    profile_id: uuid.UUID,
    job_id: uuid.UUID | None = None,
    new_job: NewJob | None = None,
    template_id: str | None = None,
) -> TailorResult:
    """`template_id` falls back to classic; the router passes the user's default."""
    profile = await get_profile(profiles, profile_id)
    source = CvContent.model_validate(profile.content)
    template = await require_template(renderer, template_id or DEFAULT_TEMPLATE_ID)
    if job_id is not None:
        job = await get_job(jobs, job_id)
    else:
        assert new_job is not None  # noqa: S101 - the router requires one of the two
        job = await create_job(
            jobs,
            description=new_job.description,
            title=new_job.title,
            company=new_job.company,
            url=new_job.url,
        )

    analysis = await ensure_analysis(jobs, job, choice, runs)
    result = await tasks.tailor_cv(
        choice,
        runs,
        profile=source,
        analysis=analysis,
        description=job.description,
        target_pages=template.target_pages,
    )
    report = factguard.check(source, result.output.content)
    content = report.content.model_dump(mode="json")
    document = await documents.create(
        profile_id=profile.id,
        job_id=job.id,
        name=document_name(job),
        template_id=template.id,
        content=content,
    )
    await versions.create(document_id=document.id, reason="tailor", content=content)

    rationales = {change.source_id: change.rationale for change in result.output.changes}
    changes, dropped = compare(source, report.content, rationales)
    missing = list(dict.fromkeys(k.strip() for k in result.output.missing_keywords if k.strip()))
    return TailorResult(
        document=document,
        job=job,
        choice=choice,
        model=result.model,
        issues=report.issues,
        changes=changes,
        dropped=dropped,
        placeholders=find_placeholders(report.content),
        missing_keywords=missing,
    )
