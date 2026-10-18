"""The AI tasks: build the request, call the provider, record the run (docs/BACKEND.md, Tasks).

Every call writes an ai_runs row, successful or not, with ids, tokens, cost and duration only.
Prompts and outputs are never logged.
"""

import logging
import time
import uuid
from collections.abc import Sequence
from typing import Any, Protocol

from pydantic import BaseModel

from api.ai.pricing import cost_usd
from api.ai.prompts import analyze_job as analyze_prompt
from api.ai.prompts import edit_cv as edit_prompt
from api.ai.prompts import extract_profile as extract_prompt
from api.ai.prompts import tailor_cv as tailor_prompt
from api.errors import ProviderError, ProviderTimeout
from api.ports.llm.base import LLMProvider, LLMRequest, LLMResult
from api.services.ai_models import ModelChoice
from cvcore.ai import BulletChange, CvEdit, ImportedCv, JobAnalysis, TailoredCv
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
        missing_keywords=wire.missing_keywords,
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
