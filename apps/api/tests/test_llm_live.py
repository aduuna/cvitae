"""Real calls to Claude and Gemini (the M3 done-when check). Never part of the default run.

uv run pytest -m live apps/api/tests/test_llm_live.py -s

Keys come from the environment or the repository's .env (ANTHROPIC_API_KEY, GEMINI_API_KEY,
MIMO_API_KEY); a model whose provider has no key is skipped. Each test prints tokens and cost. Run
one model with -k, for example -k mimo-flash.
"""

import uuid
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from api.ai import tasks
from api.ai.models import AiModel
from api.main import build_providers
from api.services.ai_models import ModelChoice
from api.settings import Settings
from cvcore import factguard
from cvcore.models import CvContent
from cvcore.render import iter_bullets
from cvcore.richtext import plain_text

pytestmark = pytest.mark.live

FIXTURES = Path(__file__).resolve().parents[3] / "templates" / "fixtures"
SAMPLE = CvContent.model_validate_json((FIXTURES / "profile-sample.json").read_text())
JOB_AD = (FIXTURES / "job-data-engineer.txt").read_text()


class MemoryRuns:
    """Stands in for AiRunRepository: keeps run records in memory."""

    user_id = uuid.uuid4()

    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    async def checkpoint(self) -> None:
        pass

    async def record(self, **values: Any) -> None:
        self.records.append(values)


def make_choice(model: AiModel) -> ModelChoice:
    """A real provider from the environment or the repository's .env, as the app builds it."""
    settings = Settings(env="test", auth_mode="dev", database_url="postgresql+psycopg://unused")
    registry = build_providers(settings)
    option = registry.option(model)
    if option is None:
        pytest.skip(f"no API key for {model}")
    return ModelChoice(option=option, provider=registry.provider(option))


def report(runs: MemoryRuns) -> None:
    for run in runs.records:
        print(
            f"\n{run['provider']} {run['task']} {run['model']}: {run['status']}, "
            f"{run.get('input_tokens', 0)} in, {run.get('output_tokens', 0)} out, "
            f"${run.get('cost_usd')}, {run.get('duration_ms')} ms"
        )
        assert run["status"] == "succeeded"
        assert run["cost_usd"] is not None and run["cost_usd"] > Decimal(0)


def roles(content: CvContent) -> list[tuple[str, str, str, str | None]]:
    return [
        (item.org, item.role, item.dates.start, item.dates.end)
        for section in content.sections
        for item in section.experience
    ]


def words(text: str) -> str:
    return " ".join(plain_text(text).split()).casefold()


@pytest.mark.parametrize("model", list(AiModel))
async def test_import_matches_the_sample_cv(model: AiModel) -> None:
    choice, runs = make_choice(model), MemoryRuns()

    result = await tasks.extract_profile(
        choice,
        runs,
        text=None,
        pdf=(FIXTURES / "sample-cv.pdf").read_bytes(),
    )

    report(runs)
    draft = result.output.content
    assert result.output.profile_name
    assert SAMPLE.basics.name not in result.output.profile_name
    assert draft.basics.name == SAMPLE.basics.name
    assert roles(draft) == roles(SAMPLE)
    assert {words(b.text) for b in iter_bullets(draft)} == {
        words(b.text) for b in iter_bullets(SAMPLE)
    }


@pytest.mark.parametrize("model", list(AiModel))
async def test_tailoring_leaves_no_unflagged_violations(model: AiModel) -> None:
    choice, runs = make_choice(model), MemoryRuns()

    analysis = (await tasks.analyze_job(choice, runs, description=JOB_AD)).output
    tailored = (
        await tasks.tailor_cv(
            choice,
            runs,
            profile=SAMPLE,
            analysis=analysis,
            description=JOB_AD,
            target_pages=1,
        )
    ).output
    guarded = factguard.check(SAMPLE, tailored.content)

    report(runs)
    print(f"fact guard corrected {len(guarded.issues)}: {[i.kind for i in guarded.issues]}")
    # Whatever the model did, the guarded CV passes the guard untouched: nothing is left unflagged.
    assert factguard.check(SAMPLE, guarded.content).issues == []
    sources = {b.id for b in iter_bullets(SAMPLE)}
    assert all(
        b.source_id in sources or b.text.startswith("[[") for b in iter_bullets(guarded.content)
    )
