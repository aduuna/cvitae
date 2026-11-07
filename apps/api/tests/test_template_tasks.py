"""The pieces under custom templates: the task runner's combined run, the prompts, the Claude-only
model choice, the PDF helpers and the fake renderer's PDF."""

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pypdfium2
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.ai import tasks
from api.ai.models import AiModel, model_options
from api.ai.prompts import template as prompt
from api.ai.prompts.common import DATA_NOT_INSTRUCTIONS
from api.billing.plans import Plan
from api.db.models import AiRun, User
from api.errors import ClaudeUnavailable, ProviderTimeout, ValidationFailed
from api.ports.auth import Identity
from api.ports.llm.base import ProviderName, provider_failure
from api.ports.llm.fake import FakeLLMProvider
from api.ports.llm.pages import pdf_text, pdf_to_pngs
from api.ports.llm.registry import ProviderRegistry
from api.ports.renderer import fake_pdf
from api.repositories.ai_runs import AiRunRepository
from api.repositories.users import UserRepository
from api.services.ai_models import ModelChoice, choose_claude_model
from api.services.user_templates import load_kit
from api.services.users import ensure_user
from api.settings import Settings

REPO = Path(__file__).resolve().parents[3]
LIBRARY = prompt.Library(helpers="#let sections(cv) = []", example='#import "/_lib/cv.typ": *')


@pytest.fixture
async def runs(db_session: AsyncSession) -> AiRunRepository:
    user = await ensure_user(UserRepository(db_session), Identity(uid="u1", email="a@x.com"))
    return AiRunRepository(db_session, user.id)


async def all_runs(session: AsyncSession) -> list[AiRun]:
    return list((await session.scalars(select(AiRun))).all())


def claude_choice(
    providers: ProviderRegistry, model: AiModel = AiModel.claude_haiku
) -> ModelChoice:
    option = providers.option(model)
    assert option is not None
    return ModelChoice(option=option, provider=providers.provider(option))


async def test_a_combined_run_is_one_row_with_the_calls_summed(
    runs: AiRunRepository, providers: ProviderRegistry, db_session: AsyncSession
) -> None:
    async with tasks.combined_run(runs) as run:
        for _ in range(3):
            await tasks.repair_template(
                claude_choice(providers),
                run,
                source="#let x = 1",
                problems=["p"],
                library=LIBRARY,
            )
        assert run.calls == 3

    [row] = await all_runs(db_session)
    assert (row.task, row.provider, row.model, row.status) == (
        "template",
        "claude",
        "claude-haiku-5-5",
        "succeeded",
    )
    assert row.prompt_version == prompt.PROMPT_VERSION
    assert row.input_tokens > 0 and row.output_tokens > 0
    assert row.error_code is None and row.cost_usd is not None and row.cost_usd > Decimal(0)
    assert row.duration_ms == 3


async def test_a_combined_run_that_raises_is_one_failed_row_with_the_errors_code(
    runs: AiRunRepository,
    providers: ProviderRegistry,
    claude: FakeLLMProvider,
    db_session: AsyncSession,
) -> None:
    with pytest.raises(ProviderTimeout):
        async with tasks.combined_run(runs) as run:
            await tasks.repair_template(
                claude_choice(providers), run, source="s", problems=[], library=LIBRARY
            )
            claude.fail_with = ProviderTimeout(
                "slow", {"provider": "claude", "error_code": "timeout"}
            )
            await tasks.repair_template(
                claude_choice(providers), run, source="s", problems=[], library=LIBRARY
            )

    [row] = await all_runs(db_session)
    assert (row.status, row.error_code) == ("failed", "timeout")
    assert row.input_tokens > 0, "the first call's tokens are kept"


async def test_a_combined_run_that_raises_something_else_is_a_failed_row(
    runs: AiRunRepository, providers: ProviderRegistry, db_session: AsyncSession
) -> None:
    with pytest.raises(RuntimeError):
        async with tasks.combined_run(runs) as run:
            await tasks.repair_template(
                claude_choice(providers), run, source="s", problems=[], library=LIBRARY
            )
            raise RuntimeError("boom")

    [row] = await all_runs(db_session)
    assert (row.status, row.error_code) == ("failed", "internal_error")


async def test_a_combined_run_without_calls_writes_nothing(
    runs: AiRunRepository, db_session: AsyncSession
) -> None:
    async with tasks.combined_run(runs):
        pass
    with pytest.raises(ValidationFailed):
        async with tasks.combined_run(runs):
            raise ValidationFailed("refused before any call")

    assert await all_runs(db_session) == []


async def test_a_failed_call_inside_a_run_that_recovers_still_succeeds(
    runs: AiRunRepository,
    providers: ProviderRegistry,
    claude: FakeLLMProvider,
    db_session: AsyncSession,
) -> None:
    async with tasks.combined_run(runs) as run:
        claude.fail_with = provider_failure(ProviderName.claude, "rate_limited")
        with pytest.raises(Exception, match="busy"):
            await tasks.refine_template(
                claude_choice(providers),
                run,
                pdf=b"%PDF",
                page=b"png",
                source="s",
                library=LIBRARY,
            )

    [row] = await all_runs(db_session)
    assert (row.status, row.error_code) == ("succeeded", None)


async def test_template_requests_carry_the_pdf_the_picture_and_the_source(
    runs: AiRunRepository, providers: ProviderRegistry, claude: FakeLLMProvider
) -> None:
    choice = claude_choice(providers, AiModel.claude_sonnet)
    async with tasks.combined_run(runs) as run:
        await tasks.draft_template(choice, run, pdf=b"%PDF-draft", library=LIBRARY)
        await tasks.repair_template(
            choice, run, source="SOURCE", problems=["first", "second"], library=LIBRARY
        )
        await tasks.refine_template(
            choice, run, pdf=b"%PDF-draft", page=b"PNG", source="SOURCE", library=LIBRARY
        )

    draft, repair, refine = claude.requests
    assert {r.task for r in claude.requests} == {"template"}
    assert {r.model for r in claude.requests} == {"claude-sonnet-5-5"}
    assert (draft.document, draft.images) == (b"%PDF-draft", ())
    assert (repair.document, repair.images) == (None, ())
    assert "- first\n- second" in repair.user_text and "<template>\nSOURCE\n" in repair.user_text
    assert (refine.document, refine.images) == (b"%PDF-draft", (b"PNG",))
    assert "<template>\nSOURCE\n" in refine.user_text


def test_the_prompt_teaches_the_contract_and_treats_the_pdf_as_data() -> None:
    system = prompt.system(prompt.Library(helpers="HELPERS-SOURCE", example="EXAMPLE-SOURCE"))

    for rule in (
        '#import "/_lib/cv.typ": *',
        '#let cv = json("data.json")',
        "paper-size()",
        "sections(cv,",
        'src("basics"',
        "Geist, Geist Mono, Libertinus Serif",
        "No images",
        "at most 40 characters",
        "one column",
    ):
        assert rule in system, rule
    assert "HELPERS-SOURCE" in system and "EXAMPLE-SOURCE" in system
    assert DATA_NOT_INSTRUCTIONS in system
    assert "\u2014" not in system


def test_the_prompt_builders_keep_the_source_in_data_tags() -> None:
    assert "attached CV" in prompt.build_draft()
    repair = prompt.build_repair("SRC", ["a", "b"])
    refine = prompt.build_refine("SRC")

    assert "<problems>\n- a\n- b\n</problems>" in repair
    assert repair.endswith("<template>\nSRC\n</template>")
    assert refine.endswith("<template>\nSRC\n</template>")
    assert "unchanged" in refine


def user(preferred: str | None = None) -> User:
    return User(firebase_uid="u", email="a@x.com", preferred_ai_model=preferred)


@pytest.mark.parametrize(
    ("preferred", "plan", "enforce", "expected"),
    [
        (None, "free", True, AiModel.claude_haiku),
        (None, "pro", True, AiModel.claude_sonnet),
        (None, "free", False, AiModel.claude_sonnet),
        ("mimo-flash", "pro", True, AiModel.claude_sonnet),
        ("gemini-flash", "free", True, AiModel.claude_haiku),
        ("claude-haiku", "pro", True, AiModel.claude_haiku),
        ("claude-sonnet", "pro", True, AiModel.claude_sonnet),
        ("claude-sonnet", "free", True, AiModel.claude_haiku),
        ("claude-sonnet", "free", False, AiModel.claude_sonnet),
    ],
)
def test_templates_always_run_on_claude(
    providers: ProviderRegistry, preferred: str | None, plan: Plan, enforce: bool, expected: AiModel
) -> None:
    choice = choose_claude_model(providers, user(preferred), enforce_plans=enforce, plan=plan)

    assert choice.option.id == expected
    assert choice.option.provider == ProviderName.claude
    assert choice.provider.name == ProviderName.claude


def test_without_an_anthropic_key_there_is_no_claude_choice(
    mimo: FakeLLMProvider, settings: Settings
) -> None:
    others = ProviderRegistry({ProviderName.mimo: mimo}, model_options(settings))

    with pytest.raises(ClaudeUnavailable, match="needs Claude"):
        choose_claude_model(others, user(), enforce_plans=True, plan="pro")


def test_the_kit_reads_the_templates_directory() -> None:
    kit = load_kit(REPO / "templates")

    assert "#let sections(" in kit.library.helpers
    assert kit.library.example.startswith("// Classic")
    assert [p.basics.name for p in kit.profiles] == ["Ama Owusu-Mensah", "Zoë O'Brien-Nkrumah"]


def test_pdf_text_reads_the_text_layer_and_the_page_count() -> None:
    text, pages = pdf_text((REPO / "templates" / "fixtures" / "sample-cv.pdf").read_bytes())

    assert pages == 1
    assert text.startswith("Ama Owusu-Mensah")
    with pytest.raises(ValidationFailed, match="could not be read"):
        pdf_text(b"%PDF-1.7 truncated")


def test_the_fake_renderers_pdf_is_a_real_pdf_holding_the_cvs_text() -> None:
    data: dict[str, Any] = json.loads(
        json.dumps(
            {
                "basics": {"name": "Zoë (Z) O'Brien\\", "links": []},
                "summary": [{"t": "Builds (nested) things", "b": False, "p": False}],
                "sections": [{"id": "abc", "kind": "skills", "title": "Skills"}],
            }
        )
    )

    pdf = fake_pdf(data)
    text, pages = pdf_text(pdf)

    assert pdf.startswith(b"%PDF-") and pages == 1
    assert "Zoë (Z) O'Brien\\" in text.replace("\r\n", " ")
    assert "Builds (nested) things" in text.replace("\r\n", " ")
    assert "Skills" in text and "abc" not in text
    [png] = pdf_to_pngs(pdf, 1)
    assert png.startswith(b"\x89PNG")
    document = pypdfium2.PdfDocument(pdf)
    assert len(document) == 1
    document.close()
