"""Drafted answers for the browser extension (docs/BACKEND.md, Drafted answers).

Drafts follow their own rule, not the CV rule: they may infer skills the applicant very likely has
and say which. The fact guard never runs on them; cvcore.answers only turns new numbers into
placeholders, fits each draft to its limits and works out the skills hint. Nothing is saved: the
only row written is the ai_runs record.
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from api.ai import tasks
from api.ai.prompts.draft_answers import JobAd, Question
from api.billing.plans import Plan
from api.repositories.ai_runs import AiRunRepository
from api.repositories.documents import DocumentRepository
from api.repositories.jobs import JobRepository
from api.repositories.profiles import ProfileRepository
from api.services.ai_models import ModelChoice
from api.services.documents import get_document
from api.services.jobs import get_job
from api.services.profiles import get_profile
from api.services.quotas import require_ai_runs
from cvcore.ai import JobAnalysis
from cvcore.answers import FinishedAnswer, Limits, Material, finish, for_drafting
from cvcore.models import CvContent


@dataclass(frozen=True)
class Source:
    kind: Literal["profile", "document"]
    id: uuid.UUID


@dataclass(frozen=True)
class AnswersResult:
    answers: list[FinishedAnswer]
    """One per question, in the order asked."""
    choice: ModelChoice
    model: str
    """The model id that answered."""


async def _material(
    profiles: ProfileRepository, documents: DocumentRepository, source: Source
) -> CvContent:
    if source.kind == "profile":
        row = await get_profile(profiles, source.id)
    else:
        row = await get_document(documents, source.id)
    return CvContent.model_validate(row.content)


def _keywords(analysis: JobAnalysis | None) -> list[str]:
    if analysis is None:
        return []
    return [*analysis.must_have, *analysis.nice_to_have, *analysis.keywords]


async def draft_answers(
    choice: ModelChoice,
    runs: AiRunRepository,
    profiles: ProfileRepository,
    documents: DocumentRepository,
    jobs: JobRepository,
    *,
    source: Source,
    questions: Sequence[Question],
    job_id: uuid.UUID | None = None,
    job: JobAd | None = None,
    plan: Plan,
) -> AnswersResult:
    """Draft an answer to each question from the profile or CV and the job ad: the saved job
    `job_id` when given, else `job`, the ad read from the page. Takes one AI run."""
    content = await _material(profiles, documents, source)
    analysis = None
    if job_id is not None:
        saved = await get_job(jobs, job_id)
        job = JobAd(description=saved.description, title=saved.title, company=saved.company)
        analysis = JobAnalysis.model_validate(saved.analysis) if saved.analysis else None
    await require_ai_runs(runs, plan)

    result = await tasks.draft_answers(
        choice,
        runs,
        material=for_drafting(content),
        questions=questions,
        job=job,
        analysis=analysis,
    )
    drafts = {draft.id: draft for draft in result.output.answers}
    material = Material(content, job.description if job else "")
    keywords = _keywords(analysis)
    answers = []
    for question in questions:
        draft = drafts.get(question.id)
        answers.append(
            finish(
                question.id,
                draft.text if draft else "",
                draft.skills if draft else [],
                question=question.text,
                limits=Limits(
                    multiline=not question.single_line,
                    max_words=question.max_words,
                    max_chars=question.max_chars,
                ),
                material=material,
                keywords=keywords,
            )
        )
    return AnswersResult(answers=answers, choice=choice, model=result.model)
