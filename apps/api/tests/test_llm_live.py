"""Real calls to the AI providers (the M3 done-when check, AI edits, drafted answers and custom
templates). Never run by default.

uv run pytest -m live apps/api/tests/test_llm_live.py -s

Keys come from the environment or the repository's .env (ANTHROPIC_API_KEY, GEMINI_API_KEY,
MIMO_API_KEY); a model whose provider has no key is skipped. Each test prints tokens and cost. Run
one model with -k, for example -k mimo-flash.
"""

import json
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from api.ai import tasks
from api.ai.models import AiModel
from api.ai.prompts.draft_answers import JobAd, Question
from api.main import build_providers
from api.ports.llm.pages import pdf_text, pdf_to_pngs
from api.services.ai_models import ModelChoice
from api.services.user_templates import _verify, load_kit
from api.settings import Settings
from cvcore import factguard
from cvcore.answers import Limits, Material, finish, for_drafting, word_count
from cvcore.models import CvContent
from cvcore.render import iter_bullets
from cvcore.rendering import Paper, RenderRequest
from cvcore.richtext import plain_text
from cvcore.user_templates import reference_from_text
from renderer.compile import render
from renderer.settings import Settings as RendererSettings

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


@pytest.mark.parametrize("model", list(AiModel))
async def test_an_edit_changes_only_what_was_asked(model: AiModel) -> None:
    choice, runs = make_choice(model), MemoryRuns()

    edit = (
        await tasks.edit_cv(
            choice,
            runs,
            cv=SAMPLE,
            request="Shorten the summary to one sentence.",
            focus="the summary",
        )
    ).output
    guarded = factguard.check(SAMPLE, edit.content, where="your CV")

    report(runs)
    print(f"reply: {edit.reply}\nfact guard corrected {[i.kind for i in guarded.issues]}")
    assert edit.reply
    assert len(plain_text(edit.content.summary)) < len(plain_text(SAMPLE.summary))
    # Everything else comes back as it was, ids included.
    assert [(b.id, words(b.text)) for b in iter_bullets(edit.content)] == [
        (b.id, words(b.text)) for b in iter_bullets(SAMPLE)
    ]
    assert roles(edit.content) == roles(SAMPLE)


@pytest.mark.parametrize("model", list(AiModel))
async def test_drafted_answers_fit_their_questions(model: AiModel) -> None:
    choice = make_choice(model)
    runs = MemoryRuns()
    questions = [
        Question(id="q1", text="Describe a time you used Databricks in production.", max_words=120),
        Question(
            id="q2",
            text="Why do you want to work at Lumen Payments?",
            single_line=True,
            max_chars=300,
        ),
        Question(id="q3", text="What are your salary expectations?"),
    ]
    # The fixture ad is for Lumen Payments, a made-up company.
    job = JobAd(description=JOB_AD, title="Senior data engineer", company="Lumen Payments")

    result = await tasks.draft_answers(
        choice, runs, material=for_drafting(SAMPLE), questions=questions, job=job
    )

    report(runs)
    drafts = {draft.id: draft for draft in result.output.answers}
    material = Material(SAMPLE, JOB_AD)
    finished = {}
    for question in questions:
        draft = drafts.get(question.id)
        finished[question.id] = finish(
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
        )
        print(f"\n{question.text}\n{finished[question.id].model_dump_json(indent=2)}")
    first, second, salary = finished["q1"], finished["q2"], finished["q3"]
    assert first.text and word_count(first.text) <= 120
    # Databricks is not in the sample profile: the hint names it.
    assert "databricks" in [skill.skill.casefold() for skill in first.inferred]
    assert second.text and "\n" not in second.text and len(second.text) <= 300
    assert salary.text == "", "questions only the applicant can answer stay empty"
    assert all("\u2014" not in answer.text for answer in finished.values())


class InProcessRenderer:
    """The real Typst renderer, run in this process, as the api's renderer port."""

    async def render_pdf(
        self, template_id: str, data: dict[str, Any], paper: Paper, *, source: str | None = None
    ) -> bytes:
        assert source is not None
        request = RenderRequest(
            files={"main.typ": source, "data.json": json.dumps(data)}, format="pdf", paper=paper
        )
        output = await render(request, RendererSettings())
        assert output.pdf is not None
        return output.pdf


@pytest.mark.parametrize("model", [AiModel.claude_haiku, AiModel.claude_sonnet])
async def test_a_template_is_drafted_from_the_sample_cv(model: AiModel) -> None:
    """The draft is tested like the pipeline tests it, with the real renderer, and one repair is
    allowed. Prints what the first draft got wrong, to judge the prompt."""
    choice, runs = make_choice(model), MemoryRuns()
    kit = load_kit(FIXTURES.parent)
    pdf = (FIXTURES / "sample-cv.pdf").read_bytes()
    reference = reference_from_text(pdf_text(pdf)[0])
    renderer: Any = InProcessRenderer()

    async with tasks.combined_run(runs) as run:
        drafted = (await tasks.draft_template(choice, run, pdf=pdf, library=kit.library)).output
        target = min(max(drafted.target_pages, 1), 2)
        verdict = await _verify(
            renderer, kit, reference, "u-liveliveli", drafted.main_typ, drafted.paper, target
        )
        print(f"\n{drafted.name!r}: {drafted.description}")
        print(f"first draft problems: {[str(p) for p in verdict.problems]}")
        source = drafted.main_typ
        if verdict.problems:
            source = (
                await tasks.repair_template(
                    choice,
                    run,
                    source=source,
                    problems=[str(p) for p in verdict.problems],
                    library=kit.library,
                )
            ).output.main_typ
            verdict = await _verify(
                renderer, kit, reference, "u-liveliveli", source, drafted.paper, target
            )
        if verdict.pdf is not None:
            refined = (
                await tasks.refine_template(
                    choice,
                    run,
                    pdf=pdf,
                    page=pdf_to_pngs(verdict.pdf, 1)[0],
                    source=source,
                    library=kit.library,
                )
            ).output.main_typ
            print(f"refinement changed the source: {refined.strip() != source.strip()}")

    [record] = runs.records
    print(
        f"{record['provider']} {record['task']} {record['model']}: {record['status']}, "
        f"{record['input_tokens']} in, {record['output_tokens']} out, ${record['cost_usd']}, "
        f"{record['duration_ms']} ms"
    )
    assert record["status"] == "succeeded"
    assert [str(p) for p in verdict.problems] == []
    assert drafted.paper in ("a4", "us-letter") and drafted.name and drafted.description
