"""The AI tasks: build the request, call the provider, record the run (docs/BACKEND.md, Tasks).

Every call writes an ai_runs row, successful or not, with ids, tokens, cost and duration only.
Prompts and outputs are never logged.
"""

import logging
import time
import uuid
from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Any, Protocol

from pydantic import BaseModel

from api.ai.models import AiModel
from api.ai.pricing import cost_usd
from api.ai.prompts import analyze_job as analyze_prompt
from api.ai.prompts import draft_answers as answers_prompt
from api.ai.prompts import edit_cv as edit_prompt
from api.ai.prompts import extract_profile as extract_prompt
from api.ai.prompts import tailor_cv as tailor_prompt
from api.ai.prompts import template as template_prompt
from api.errors import AppError, ProviderError, ProviderTimeout
from api.ports.llm.base import Effort, LLMProvider, LLMRequest, LLMResult
from api.services.ai_models import ModelChoice
from cvcore.ai import (
    BulletChange,
    CvEdit,
    DraftAnswers,
    GeneratedTemplate,
    ImportedCv,
    JobAnalysis,
    RevisedTemplate,
    TailoredCv,
)
from cvcore.models import CvContent
from cvcore.wire import WireCvEdit, WireImportedCv, WireTailoredCv, from_wire

logger = logging.getLogger(__name__)


class RunRecorder(Protocol):
    """Where runs are recorded: AiRunRepository, or a stand-in in live tests."""

    user_id: uuid.UUID

    async def checkpoint(self) -> None: ...

    async def record(self, **values: Any) -> object: ...


async def run[T: BaseModel](
    provider: LLMProvider, runs: RunRecorder, request: LLMRequest[T], prompt_version: str
) -> LLMResult[T]:
    await runs.checkpoint()
    model = request.model
    started = time.monotonic()
    try:
        result = await provider.generate(request)
    except (ProviderError, ProviderTimeout) as exc:
        error_code = str(exc.details.get("error_code", exc.code))
        duration_ms = int((time.monotonic() - started) * 1000)
        await runs.record(
            task=request.task,
            provider=str(provider.name),
            model=model,
            prompt_version=prompt_version,
            status="failed",
            error_code=error_code,
            duration_ms=duration_ms,
        )
        logger.warning(
            "ai run failed",
            extra={
                "user_id": str(runs.user_id),
                "task": request.task,
                "provider": str(provider.name),
                "model": model,
                "error_code": error_code,
                "duration_ms": duration_ms,
            },
        )
        raise
    cost = cost_usd(result.model, result.input_tokens, result.output_tokens)
    await runs.record(
        task=request.task,
        provider=str(result.provider),
        model=result.model,
        prompt_version=prompt_version,
        status="succeeded",
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        cost_usd=cost,
        duration_ms=result.duration_ms,
    )
    logger.info(
        "ai run",
        extra={
            "user_id": str(runs.user_id),
            "task": request.task,
            "provider": str(result.provider),
            "model": result.model,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "cost_usd": str(cost) if cost is not None else None,
            "duration_ms": result.duration_ms,
        },
    )
    return result


def _with_output[T: BaseModel](result: LLMResult[Any], output: T) -> LLMResult[T]:
    return LLMResult(
        output=output,
        provider=result.provider,
        model=result.model,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        duration_ms=result.duration_ms,
    )


async def extract_profile(
    choice: ModelChoice, runs: RunRecorder, *, text: str | None, pdf: bytes | None
) -> LLMResult[ImportedCv]:
    # Providers write the flat wire shape (cvcore.wire); the app works with CvContent.
    request = LLMRequest(
        task="import",
        system=extract_prompt.SYSTEM,
        user_text=extract_prompt.build(text),
        output_model=WireImportedCv,
        model=choice.option.model,
        document=pdf,
        effort="low",
    )
    result = await run(choice.provider, runs, request, extract_prompt.PROMPT_VERSION)
    wire = result.output
    imported = ImportedCv(content=from_wire(wire.content), profile_name=wire.profile_name)
    return _with_output(result, imported)


async def analyze_job(
    choice: ModelChoice,
    runs: RunRecorder,
    *,
    description: str,
    title: str = "",
    company: str = "",
) -> LLMResult[JobAnalysis]:
    request = LLMRequest(
        task="analyze_job",
        system=analyze_prompt.SYSTEM,
        user_text=analyze_prompt.build(description, title, company),
        output_model=JobAnalysis,
        model=choice.option.analysis_model,
        effort="low",
        max_output_tokens=4000,
    )
    return await run(choice.provider, runs, request, analyze_prompt.PROMPT_VERSION)


async def tailor_cv(
    choice: ModelChoice,
    runs: RunRecorder,
    *,
    profile: CvContent,
    analysis: JobAnalysis,
    description: str,
    target_pages: int,
) -> LLMResult[TailoredCv]:
    request = LLMRequest(
        task="tailor",
        system=tailor_prompt.SYSTEM,
        user_text=tailor_prompt.build(profile, analysis, description, target_pages),
        output_model=WireTailoredCv,
        model=choice.option.model,
    )
    result = await run(choice.provider, runs, request, tailor_prompt.PROMPT_VERSION)
    wire = result.output
    tailored = TailoredCv(
        content=from_wire(wire.content),
        changes=[BulletChange(source_id=c.source_id, rationale=c.rationale) for c in wire.changes],
    )
    return _with_output(result, tailored)


async def edit_cv(
    choice: ModelChoice,
    runs: RunRecorder,
    *,
    cv: CvContent,
    request: str,
    history: Sequence[edit_prompt.Turn] = (),
    focus: str | None = None,
) -> LLMResult[CvEdit]:
    llm_request = LLMRequest(
        task="edit",
        system=edit_prompt.SYSTEM,
        user_text=edit_prompt.build(cv, request, history, focus),
        output_model=WireCvEdit,
        model=choice.option.model,
        effort="low",
    )
    result = await run(choice.provider, runs, llm_request, edit_prompt.PROMPT_VERSION)
    wire = result.output
    # The reply is shown as plain text; models sometimes quote the CV's bold markers in it.
    reply = wire.reply.replace("**", "").strip()
    return _with_output(result, CvEdit(reply=reply, content=from_wire(wire.content)))


async def draft_answers(
    choice: ModelChoice,
    runs: RunRecorder,
    *,
    material: CvContent,
    questions: Sequence[answers_prompt.Question],
    job: answers_prompt.JobAd | None = None,
    analysis: JobAnalysis | None = None,
) -> LLMResult[DraftAnswers]:
    """Drafts for application questions. Not CV content: no fact guard runs on them."""
    request = LLMRequest(
        task="answers",
        system=answers_prompt.SYSTEM,
        user_text=answers_prompt.build(material, questions, job, analysis),
        output_model=DraftAnswers,
        model=choice.option.model,
        effort="low",
        max_output_tokens=12000,
    )
    return await run(choice.provider, runs, request, answers_prompt.PROMPT_VERSION)


class CombinedRun:
    """Records several provider calls as one `ai_runs` row, for work that takes more than one
    call yet is one AI run to the user (a custom template: draft, repairs, refinement). It stands
    in for the run recorder: `run()` hands it each call's values, and `finish` writes the one row,
    with tokens, cost and duration summed."""

    def __init__(self, runs: RunRecorder) -> None:
        self._runs = runs
        self.user_id = runs.user_id
        self._calls: list[dict[str, Any]] = []

    async def checkpoint(self) -> None:
        await self._runs.checkpoint()

    async def record(self, **values: Any) -> None:
        self._calls.append(values)

    @property
    def calls(self) -> int:
        return len(self._calls)

    async def finish(self, *, succeeded: bool, error_code: str | None = None) -> None:
        """Write the row. The model and provider are the last call's; a failed row carries
        `error_code`, else the code of the last failed call."""
        if not self._calls:
            return
        last = self._calls[-1]
        costs = [c["cost_usd"] for c in self._calls if c.get("cost_usd") is not None]
        await self._runs.record(
            task=last["task"],
            provider=last["provider"],
            model=last["model"],
            prompt_version=last["prompt_version"],
            status="succeeded" if succeeded else "failed",
            error_code=None if succeeded else (error_code or last.get("error_code")),
            input_tokens=sum(c.get("input_tokens", 0) for c in self._calls),
            output_tokens=sum(c.get("output_tokens", 0) for c in self._calls),
            cost_usd=sum(costs, Decimal(0)) if costs else None,
            duration_ms=sum(c.get("duration_ms", 0) for c in self._calls),
        )


@asynccontextmanager
async def combined_run(runs: RunRecorder) -> AsyncGenerator[CombinedRun]:
    """One `ai_runs` row for everything done inside: succeeded when the block returns, failed
    (with the error's code) when it raises."""
    combined = CombinedRun(runs)
    try:
        yield combined
    except AppError as exc:
        await combined.finish(
            succeeded=False, error_code=str(exc.details.get("error_code", exc.code))
        )
        raise
    except BaseException:
        await combined.finish(succeeded=False, error_code="internal_error")
        raise
    await combined.finish(succeeded=True)


TEMPLATE_MAX_OUTPUT_TOKENS = 24000
"""Room for the source and the model's thinking: Haiku spends up to 14k tokens on a draft."""


def _draft_effort(choice: ModelChoice) -> Effort:
    """Sonnet thinks little at medium and reads a design loosely; high is worth the seconds.
    Haiku already thinks for 5,000 to 20,000 tokens at medium, and low is no faster: high would
    take it past the call timeout."""
    return "high" if choice.option.id == AiModel.claude_sonnet else "medium"


async def draft_template(
    choice: ModelChoice,
    runs: RunRecorder,
    *,
    pdf: bytes,
    library: template_prompt.Library,
    measurements: str = "",
) -> LLMResult[GeneratedTemplate]:
    """A Typst template in the design of the PDF. Not CV content: no fact guard; the checks in
    cvcore.user_templates and a test render stand in for it."""
    request = LLMRequest(
        task="template",
        system=template_prompt.system(library),
        user_text=template_prompt.build_draft(measurements),
        output_model=GeneratedTemplate,
        model=choice.option.model,
        document=pdf,
        effort=_draft_effort(choice),
        max_output_tokens=TEMPLATE_MAX_OUTPUT_TOKENS,
    )
    return await run(choice.provider, runs, request, template_prompt.PROMPT_VERSION)


async def repair_template(
    choice: ModelChoice,
    runs: RunRecorder,
    *,
    source: str,
    problems: Sequence[str],
    library: template_prompt.Library,
) -> LLMResult[RevisedTemplate]:
    """The source corrected for the listed problems. Sends no CV: only the source and the
    problems, which never repeat the upload's text."""
    request = LLMRequest(
        task="template",
        system=template_prompt.system(library),
        user_text=template_prompt.build_repair(source, problems),
        output_model=RevisedTemplate,
        model=choice.option.model,
        effort="low",
    )
    return await run(choice.provider, runs, request, template_prompt.PROMPT_VERSION)


async def refine_template(
    choice: ModelChoice,
    runs: RunRecorder,
    *,
    pdf: bytes,
    page: bytes,
    source: str,
    library: template_prompt.Library,
    pdf_measurements: str = "",
    render_measurements: str = "",
) -> LLMResult[RevisedTemplate]:
    """The source corrected to match the original's design more closely, from the original PDF,
    a PNG of page 1 of the template rendered with sample data and the measurements of both."""
    request = LLMRequest(
        task="template",
        system=template_prompt.system(library),
        user_text=template_prompt.build_refine(source, pdf_measurements, render_measurements),
        output_model=RevisedTemplate,
        model=choice.option.model,
        document=pdf,
        images=(page,),
        max_output_tokens=TEMPLATE_MAX_OUTPUT_TOKENS,
    )
    return await run(choice.provider, runs, request, template_prompt.PROMPT_VERSION)
