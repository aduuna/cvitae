"""Custom templates: generating one from a CV, the plan limits, and using it everywhere a built-in
template works, for its owner only. The models and the renderer are fakes."""

import copy
import io
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import docx
import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.ai.models import model_options
from api.ai.prompts.common import DATA_NOT_INSTRUCTIONS
from api.db.models import AiRun, Upload, User, UserTemplate
from api.deps import get_providers
from api.ports.llm.base import LLMRequest, ProviderName, provider_failure
from api.ports.llm.fake import FAKE_TEMPLATE, FakeLLMProvider
from api.ports.llm.pages import pdf_text
from api.ports.llm.registry import ProviderRegistry
from api.ports.renderer import FakeRendererClient
from api.repositories.user_templates import UserTemplateRepository
from api.settings import Settings
from cvcore.ai import GeneratedTemplate, RevisedTemplate
from cvcore.user_templates import new_template_id

FIXTURES = Path(__file__).resolve().parents[3] / "templates" / "fixtures"
SAMPLE_PDF = (FIXTURES / "sample-cv.pdf").read_bytes()
OWNER = "Ama Owusu-Mensah"
"""The name on the uploaded CV, and in every template fixture."""

MakePro = Callable[..., Awaitable[None]]
BROKEN = FAKE_TEMPLATE + '\n#panic("the template stops here")\n'
CUSTOM = "/api/v1/templates/custom"


def drafted(source: str = FAKE_TEMPLATE, **changes: Any) -> GeneratedTemplate:
    values: dict[str, Any] = {
        "name": "Teal rule",
        "description": "Sans serif type with teal section rules and a compact header.",
        "paper": "a4",
        "target_pages": 1,
        "main_typ": source,
    } | changes
    return GeneratedTemplate(**values)


def revised(source: str = FAKE_TEMPLATE) -> RevisedTemplate:
    return RevisedTemplate(main_typ=source)


def script(*answers: BaseModel | Exception) -> Callable[[LLMRequest[Any]], BaseModel]:
    """Responders that answer the model's calls in turn; an exception is raised as the call."""
    pending = iter(answers)

    def respond(_: LLMRequest[Any]) -> BaseModel:
        answer = next(pending)
        if isinstance(answer, Exception):
            raise answer
        return answer

    return respond


def calls(provider: FakeLLMProvider) -> list[str]:
    """What each model call was: draft, repair or refine."""
    found = []
    for request in provider.requests:
        if request.output_model is GeneratedTemplate:
            found.append("draft")
        else:
            found.append("refine" if request.document is not None else "repair")
    return found


async def generate(client: AsyncClient, pdf: bytes = SAMPLE_PDF) -> Any:
    return await client.post(CUSTOM, files={"file": ("Ama CV.pdf", pdf, "application/pdf")})


async def ready(client: AsyncClient, pdf: bytes = SAMPLE_PDF) -> dict[str, Any]:
    """Generate a template and confirm it."""
    response = await generate(client, pdf)
    assert response.status_code == 201, response.text
    confirmed = await client.patch(f"{CUSTOM}/{response.json()['id']}", json={"status": "ready"})
    assert confirmed.status_code == 200, confirmed.text
    return confirmed.json()


async def runs(session: AsyncSession) -> list[AiRun]:
    return list((await session.scalars(select(AiRun).order_by(AiRun.created_at))).all())


async def stored(session: AsyncSession) -> list[UserTemplate]:
    return list((await session.scalars(select(UserTemplate))).all())


async def user_id(client: AsyncClient) -> uuid.UUID:
    return uuid.UUID((await client.get("/api/v1/me")).json()["id"])


async def seed(
    session: AsyncSession, owner: uuid.UUID, *, status: str = "ready", slug: str | None = None
) -> UserTemplate:
    row = await UserTemplateRepository(session, owner).create(
        slug=slug or new_template_id(),
        name="Seeded",
        description="",
        main_typ=FAKE_TEMPLATE,
        paper_sizes=["a4", "us-letter"],
        target_pages=1,
        status=status,
        prompt_version="x",
    )
    await session.commit()
    return row


async def profile_and_document(client: AsyncClient, content: dict[str, Any], **body: Any) -> Any:
    profile = await client.post("/api/v1/profiles", json={"name": "Data", "content": content})
    return await client.post("/api/v1/documents", json={"profile_id": profile.json()["id"], **body})


def without_placeholders(content: dict[str, Any]) -> dict[str, Any]:
    """The sample profile with its placeholder filled in, so a PDF can be exported."""
    content = copy.deepcopy(content)
    bullet = content["sections"][0]["experience"][0]["engagements"][0]["bullets"][1]
    bullet["text"] = "Built a streaming fraud-signal pipeline on Kafka."
    return content


def docx_bytes() -> bytes:
    document = docx.Document()
    document.add_paragraph("Ama Owusu-Mensah, data engineer")
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


# Generating


async def test_a_pdf_becomes_a_draft_template(
    client: AsyncClient,
    claude: FakeLLMProvider,
    mimo: FakeLLMProvider,
    gemini: FakeLLMProvider,
    db_session: AsyncSession,
) -> None:
    response = await generate(client)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["id"].startswith("u-") and len(body["id"]) == 12
    assert (body["name"], body["status"]) == ("Teal rule", "draft")
    assert body["description"] == "Sans serif type with teal section rules and a compact header."
    assert (body["paper_sizes"], body["target_pages"]) == (["a4", "us-letter"], 1)
    # Free runs it on Claude Haiku: the default model is MiMo, but this task always uses Claude.
    assert (body["ai_model"], body["provider"], body["model"]) == (
        "claude-haiku",
        "claude",
        "claude-haiku-5-5",
    )
    assert mimo.requests == [] and gemini.requests == []
    assert calls(claude) == ["draft", "refine"]
    draft, refine = claude.requests
    assert draft.task == "template" and draft.document == SAMPLE_PDF
    assert draft.system.count("sections(cv,") >= 1
    assert "paper-size()" in draft.system and "#let section-heading(title)" in draft.system
    assert DATA_NOT_INSTRUCTIONS in draft.system
    # What the PDF measures goes to the draft, and with the render's to the refinement, which
    # also sees the original and a picture of the rendered page. None of it is the CV's text.
    assert "<pdf_measurements>\n- Paper: A4 (21.0 x 29.7 cm), 1 page." in draft.user_text
    assert "#1f3a5f" in draft.user_text and OWNER.split()[0] not in draft.user_text
    assert refine.document == SAMPLE_PDF
    assert len(refine.images) == 1 and refine.images[0].startswith(b"\x89PNG")
    assert "<pdf_measurements>" in refine.user_text
    assert "<template_measurements>\n- Paper: A4 (21.0 x 29.7 cm), 1 page." in refine.user_text
    [row] = await stored(db_session)
    assert (row.slug, row.status, row.main_typ) == (body["id"], "draft", FAKE_TEMPLATE)
    assert row.upload_id is not None
    [upload] = (await client.get("/api/v1/uploads")).json()
    assert (upload["id"], upload["mime_type"]) == (str(row.upload_id), "application/pdf")
    # The two calls are one run.
    [run] = await runs(db_session)
    assert (run.task, run.status, run.provider, run.model) == (
        "template",
        "succeeded",
        "claude",
        "claude-haiku-5-5",
    )
    assert run.input_tokens == sum(len(r.user_text) // 4 for r in claude.requests)
    assert run.cost_usd is not None and run.cost_usd > 0


async def test_the_draft_is_tested_with_sample_data_and_with_empty_fields(
    client: AsyncClient, renderer: FakeRendererClient
) -> None:
    response = await generate(client)

    assert renderer.calls[0][1] == response.json()["id"]

    names = [data["basics"]["name"] for _, _, data in renderer.calls]
    assert names == [OWNER, "Zoë O'Brien-Nkrumah"]
    assert {fmt for fmt, _, _ in renderer.calls} == {"pdf"}
    # Through the user's own source, under the id it will have.
    assert renderer.sources == [FAKE_TEMPLATE] * 2
    assert len({template_id for _, template_id, _ in renderer.calls}) == 1


async def test_pro_runs_on_sonnet_and_a_chosen_claude_model_wins(
    client: AsyncClient, claude: FakeLLMProvider, make_pro: MakePro
) -> None:
    await make_pro()
    assert (await generate(client)).json()["model"] == "claude-sonnet-5-5"

    await client.patch("/api/v1/me", json={"preferred_ai_model": "claude-haiku"})
    assert (await generate(client)).json()["model"] == "claude-haiku-5-5"

    await client.patch("/api/v1/me", json={"preferred_ai_model": "gemini-flash"})
    assert (await generate(client)).json()["ai_model"] == "claude-sonnet"
    assert {request.model for request in claude.requests} == {
        "claude-sonnet-5-5",
        "claude-haiku-5-5",
    }


async def test_free_cannot_use_sonnet_for_templates_when_plans_are_enforced(
    client: AsyncClient, claude: FakeLLMProvider
) -> None:
    await client.patch("/api/v1/me", json={"preferred_ai_model": "claude-sonnet"})

    response = await generate(client)

    assert response.json()["model"] == "claude-haiku-5-5"


async def test_without_a_claude_key_it_refuses_before_any_run(
    app: FastAPI,
    client: AsyncClient,
    mimo: FakeLLMProvider,
    settings: Settings,
    db_session: AsyncSession,
) -> None:
    app.dependency_overrides[get_providers] = lambda: ProviderRegistry(
        {ProviderName.mimo: mimo}, model_options(settings)
    )

    response = await generate(client)

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "claude_unavailable"
    assert mimo.requests == []
    assert await runs(db_session) == [] and await stored(db_session) == []
    assert (await client.get("/api/v1/uploads")).json() == []


async def test_an_earlier_pdf_upload_can_be_used(
    client: AsyncClient, mimo: FakeLLMProvider, claude: FakeLLMProvider
) -> None:
    imported = await client.post(
        "/api/v1/imports", files={"file": ("Ama CV.pdf", SAMPLE_PDF, "application/pdf")}
    )
    upload_id = imported.json()["upload_id"]

    response = await client.post(CUSTOM, data={"upload_id": upload_id})

    assert response.status_code == 201, response.text
    assert response.json()["upload_id"] == upload_id
    assert claude.requests[0].document == SAMPLE_PDF
    assert len((await client.get("/api/v1/uploads")).json()) == 1


async def test_a_docx_is_refused_with_a_clear_message(
    client: AsyncClient, claude: FakeLLMProvider, db_session: AsyncSession
) -> None:
    sent = await client.post(
        CUSTOM, files={"file": ("cv.docx", docx_bytes(), "application/octet-stream")}
    )
    imported = await client.post(
        "/api/v1/imports", files={"file": ("cv.docx", docx_bytes(), "application/octet-stream")}
    )
    earlier = await client.post(CUSTOM, data={"upload_id": imported.json()["upload_id"]})

    for response in (sent, earlier):
        assert response.status_code == 422
        assert response.json()["error"]["message"] == (
            "A template copies how a CV looks, which a DOCX does not keep. Save it as a PDF "
            "and upload that."
        )
    assert claude.requests == []
    assert await stored(db_session) == []
    # Only the import's own upload exists: the refused DOCX was not stored.
    assert len((await client.get("/api/v1/uploads")).json()) == 1
    assert [run.task for run in await runs(db_session)] == ["import"]


@pytest.mark.parametrize(
    ("files", "data", "message"),
    [
        ({"file": ("x.pdf", b"not a pdf at all", "application/pdf")}, None, "not a PDF"),
        ({"file": ("x.pdf", b"%PDF-1.7 broken", "application/pdf")}, None, "could not be read"),
        (None, None, "Upload a PDF"),
        (
            {"file": ("x.pdf", SAMPLE_PDF, "application/pdf")},
            {"upload_id": str(uuid.uuid4())},
            "Upload a PDF",
        ),
    ],
)
async def test_bad_input_is_refused_before_any_run(
    client: AsyncClient,
    claude: FakeLLMProvider,
    db_session: AsyncSession,
    files: Any,
    data: Any,
    message: str,
) -> None:
    response = await client.post(CUSTOM, files=files, data=data)

    assert response.status_code == 422
    assert message in response.json()["error"]["message"]
    assert claude.requests == [] and await runs(db_session) == []


async def test_an_oversized_file_is_refused(client: AsyncClient, claude: FakeLLMProvider) -> None:
    response = await generate(client, b"%PDF-" + b"0" * (10 * 1024 * 1024))

    assert response.status_code == 422
    assert "larger than 10 MB" in response.json()["error"]["message"]
    assert claude.requests == []


async def test_another_users_upload_is_not_found(
    client: AsyncClient, other_client: AsyncClient, claude: FakeLLMProvider
) -> None:
    imported = await other_client.post(
        "/api/v1/imports", files={"file": ("cv.pdf", SAMPLE_PDF, "application/pdf")}
    )

    response = await client.post(CUSTOM, data={"upload_id": imported.json()["upload_id"]})

    assert response.status_code == 404
    assert claude.requests == []


async def test_it_needs_sign_in(make_client: Any) -> None:
    async with make_client(user=None) as anonymous:
        response = await anonymous.post(CUSTOM, files={"file": ("a.pdf", SAMPLE_PDF)})

    assert response.status_code == 401


# Repair and refinement


async def test_a_template_that_does_not_compile_is_repaired(
    client: AsyncClient, claude: FakeLLMProvider, db_session: AsyncSession
) -> None:
    claude.responders["template"] = script(drafted(BROKEN), revised(), revised())

    response = await generate(client)

    assert response.status_code == 201, response.text
    assert calls(claude) == ["draft", "repair", "refine"]
    repair = claude.requests[1]
    # The repair carries the source and the error, and no CV: not the PDF, not its text.
    assert repair.document is None and repair.images == ()
    assert "<template>" in repair.user_text and "#panic(" in repair.user_text
    assert "Typst could not compile the template at line" in repair.user_text
    assert OWNER not in repair.user_text and OWNER not in repair.system
    assert (await stored(db_session))[0].main_typ == FAKE_TEMPLATE
    assert len(await runs(db_session)) == 1


async def test_a_template_that_copies_the_cv_is_repaired_without_the_problems_repeating_it(
    client: AsyncClient, claude: FakeLLMProvider
) -> None:
    leaking = FAKE_TEMPLATE + f'\n#let owner = "{OWNER}"\n#let mail = "ama@example.com"\n'
    claude.responders["template"] = script(drafted(leaking), revised(), revised())

    response = await generate(client)

    assert response.status_code == 201
    problems = claude.requests[1].user_text.split("<problems>")[1].split("</problems>")[0]
    assert "name from the attached CV" in problems
    assert "email address from the attached CV" in problems
    assert OWNER not in problems and "ama@example.com" not in problems


async def test_a_template_that_may_not_run_is_not_rendered(
    client: AsyncClient, claude: FakeLLMProvider, renderer: FakeRendererClient
) -> None:
    reads_files = FAKE_TEMPLATE + '\n#let secret = read("/etc/passwd")\n'
    claude.responders["template"] = script(drafted(reads_files), revised(), revised())

    response = await generate(client)

    assert response.status_code == 201
    assert "read() is not allowed" in claude.requests[1].user_text
    # Nothing was rendered for the first draft; its repair was, with both CVs.
    assert renderer.sources == [FAKE_TEMPLATE] * 2


async def test_a_template_that_drops_data_is_repaired(
    client: AsyncClient, claude: FakeLLMProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    claude.responders["template"] = script(drafted(), revised(), revised())
    reads = iter(range(10))

    def without_the_summary(pdf: bytes) -> tuple[str, int]:
        text, pages = pdf_text(pdf)
        # The second read is the draft's sample CV: its render lacks the summary.
        return (text.replace("Data engineer with", "") if next(reads) == 1 else text), pages

    monkeypatch.setattr("api.services.user_templates.pdf_text", without_the_summary)

    response = await generate(client)

    assert response.status_code == 201
    assert "does not show its summary" in claude.requests[1].user_text


async def test_a_template_that_overflows_the_page_target_is_repaired(
    client: AsyncClient, claude: FakeLLMProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    claude.responders["template"] = script(drafted(), revised(), revised())
    # Page counts, per read of a PDF: the upload, then the sample and the empty CV of the draft
    # (the sample takes two pages), then of the repair.
    pages = iter([1, 2, 1, 1, 1])
    monkeypatch.setattr(
        "api.services.user_templates.pdf_text", lambda pdf: (pdf_text(pdf)[0], next(pages))
    )

    response = await generate(client)

    assert response.status_code == 201
    assert "must fit 1 page" in claude.requests[1].user_text


async def test_when_repairs_run_out_nothing_is_saved(
    client: AsyncClient,
    claude: FakeLLMProvider,
    db_session: AsyncSession,
    make_pro: MakePro,
) -> None:
    claude.responders["template"] = script(drafted(BROKEN), revised(BROKEN), revised(BROKEN))

    response = await generate(client)

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "template_failed"
    assert error["details"]["issues"] == ["compile_error"]
    assert calls(claude) == ["draft", "repair", "repair"]
    assert await stored(db_session) == []
    assert (await client.get("/api/v1/uploads")).json() == []
    # Free counts every attempt: one failed run, and no token detail beyond the sums.
    [run] = await runs(db_session)
    assert (run.status, run.error_code, run.task) == ("failed", "template_failed", "template")
    assert (await client.get("/api/v1/usage")).json()["ai_runs"]["used"] == 1


async def test_pro_does_not_pay_a_run_for_a_failed_generation(
    client: AsyncClient, claude: FakeLLMProvider, make_pro: MakePro
) -> None:
    await make_pro()
    claude.responders["template"] = script(drafted(BROKEN), revised(BROKEN), revised(BROKEN))

    assert (await generate(client)).status_code == 422

    assert (await client.get("/api/v1/usage")).json()["ai_runs"]["used"] == 0


async def test_a_provider_failure_saves_nothing_and_is_recorded(
    client: AsyncClient, claude: FakeLLMProvider, db_session: AsyncSession
) -> None:
    claude.fail_with = provider_failure(ProviderName.claude, "refused")

    response = await generate(client)

    assert response.status_code == 502
    error = response.json()["error"]
    assert error["code"] == "provider_error"
    assert "another model" not in error["message"]
    assert error["message"].startswith("Claude could not finish this template.")
    assert error["details"]["error_code"] == "refused"
    assert await stored(db_session) == []
    assert (await client.get("/api/v1/uploads")).json() == []
    [run] = await runs(db_session)
    assert (run.status, run.error_code, run.task) == ("failed", "refused", "template")


async def test_a_repair_that_fails_ends_the_generation(
    client: AsyncClient, claude: FakeLLMProvider, db_session: AsyncSession
) -> None:
    rate_limited = provider_failure(ProviderName.claude, "rate_limited")
    claude.responders["template"] = script(drafted(BROKEN), rate_limited)

    response = await generate(client)

    assert response.status_code == 502
    assert await stored(db_session) == []
    [run] = await runs(db_session)
    assert (run.status, run.error_code) == ("failed", "rate_limited")


async def test_a_better_refinement_is_kept(client: AsyncClient, claude: FakeLLMProvider) -> None:
    refined = FAKE_TEMPLATE + "\n// Margins tightened to match the original.\n"
    claude.responders["template"] = script(drafted(), revised(refined))

    body = (await generate(client)).json()

    source = (await client.get(f"{CUSTOM}/{body['id']}/source")).json()["main_typ"]
    assert source == refined


@pytest.mark.parametrize(
    "answer",
    [
        revised(BROKEN),
        revised(FAKE_TEMPLATE + f'\n#let owner = "{OWNER}"\n'),
        provider_failure(ProviderName.claude, "output_too_long"),
    ],
    ids=["does not compile", "fails a check", "provider fails"],
)
async def test_a_refinement_that_does_not_pass_is_dropped(
    client: AsyncClient,
    claude: FakeLLMProvider,
    db_session: AsyncSession,
    answer: BaseModel | Exception,
) -> None:
    claude.responders["template"] = script(drafted(), answer)

    response = await generate(client)

    assert response.status_code == 201
    assert (await stored(db_session))[0].main_typ == FAKE_TEMPLATE
    # The generation succeeded, so it is one successful run whatever the last call did.
    assert [run.status for run in await runs(db_session)] == ["succeeded"]


async def test_an_unchanged_refinement_is_not_tested_again(
    client: AsyncClient, renderer: FakeRendererClient
) -> None:
    await generate(client)

    # The draft's two test renders; the refinement came back as it was, so no more.
    assert len(renderer.calls) == 2


async def test_a_refinement_is_tested_like_the_draft(
    client: AsyncClient, claude: FakeLLMProvider, renderer: FakeRendererClient
) -> None:
    refined = FAKE_TEMPLATE + "\n// Spacing tightened.\n"
    claude.responders["template"] = script(drafted(), revised(refined))

    await generate(client)

    assert len(renderer.calls) == 4
    assert renderer.sources == [FAKE_TEMPLATE] * 2 + [refined] * 2


async def test_no_refinement_starts_after_the_time_budget(
    client: AsyncClient, claude: FakeLLMProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("api.services.user_templates.TIME_BUDGET_SECONDS", 0)

    response = await generate(client)

    assert response.status_code == 201
    assert calls(claude) == ["draft"]


async def test_no_repair_starts_after_the_time_budget(
    client: AsyncClient,
    claude: FakeLLMProvider,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
) -> None:
    monkeypatch.setattr("api.services.user_templates.TIME_BUDGET_SECONDS", 0)
    claude.responders["template"] = script(drafted(BROKEN))

    response = await generate(client)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "template_failed"
    assert calls(claude) == ["draft"]
    assert await stored(db_session) == []


async def test_the_name_and_description_never_name_the_owner(
    client: AsyncClient, claude: FakeLLMProvider
) -> None:
    claude.responders["template"] = script(
        drafted(name=f"{OWNER} CV", description="  Made for  ama@example.com  "), revised()
    )

    body = (await generate(client)).json()

    assert (body["name"], body["description"]) == ("Custom template", "")


async def test_names_are_trimmed_and_the_page_target_is_kept_in_range(
    client: AsyncClient, claude: FakeLLMProvider
) -> None:
    claude.responders["template"] = script(
        drafted(name="  Long   " + "x" * 100, description="d" * 300, target_pages=5), revised()
    )

    body = (await generate(client)).json()

    assert len(body["name"]) == 60 and body["name"].startswith("Long x")
    assert len(body["description"]) == 200
    assert body["target_pages"] == 2


async def test_a_new_generation_replaces_the_unconfirmed_one(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    first = (await generate(client)).json()
    second = (await generate(client)).json()

    assert [row.slug for row in await stored(db_session)] == [second["id"]]
    assert (await client.get(f"/api/v1/templates/{first['id']}/preview")).status_code == 404


async def test_a_ready_template_survives_a_new_generation(
    client: AsyncClient, db_session: AsyncSession, make_pro: MakePro
) -> None:
    await make_pro()
    kept = await ready(client)
    draft = (await generate(client)).json()

    assert {row.slug for row in await stored(db_session)} == {kept["id"], draft["id"]}


# Plan limits


async def test_free_keeps_one_template_and_asks_before_any_run(
    client: AsyncClient, claude: FakeLLMProvider, db_session: AsyncSession
) -> None:
    await ready(client)
    used = len(claude.requests)

    response = await generate(client)

    assert response.status_code == 402
    error = response.json()["error"]
    assert (error["code"], error["details"]["resource"]) == ("quota_exceeded", "templates")
    assert error["message"] == (
        "You have 1 custom template, the most on Free. Delete one or upgrade to Pro for 10."
    )
    assert len(claude.requests) == used
    assert len(await runs(db_session)) == 1
    usage = (await client.get("/api/v1/usage")).json()
    assert usage["templates"] == {"used": 1, "limit": 1, "message": error["message"]}


async def test_pro_keeps_ten(
    client: AsyncClient, claude: FakeLLMProvider, db_session: AsyncSession, make_pro: MakePro
) -> None:
    await make_pro()
    owner = await user_id(client)
    for _ in range(10):
        await seed(db_session, owner)
    used = len(claude.requests)

    response = await generate(client)

    assert response.status_code == 402
    assert response.json()["error"]["message"].startswith("You have 10 custom templates, the most")
    assert len(claude.requests) == used
    await client.delete(f"{CUSTOM}/{(await stored(db_session))[0].slug}")
    assert (await generate(client)).status_code == 201


async def test_an_unconfirmed_draft_takes_no_room(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await generate(client)

    assert (await client.get("/api/v1/usage")).json()["templates"]["used"] == 0
    # So the free user can still make another, which replaces the draft.
    assert (await generate(client)).status_code == 201


async def test_no_ai_usage_left_refuses_before_any_call(
    client: AsyncClient, claude: FakeLLMProvider, db_session: AsyncSession
) -> None:
    owner = await user_id(client)
    db_session.add_all(
        AiRun(
            user_id=owner,
            task="tailor",
            provider="mimo",
            model="m",
            prompt_version="1",
            status="succeeded",
        )
        for _ in range(20)
    )
    await db_session.commit()

    response = await generate(client)

    assert response.status_code == 402
    assert response.json()["error"]["details"]["resource"] == "ai_runs"
    assert claude.requests == []
    assert await stored(db_session) == []


async def test_a_generation_takes_one_run_of_the_allowance(
    client: AsyncClient, claude: FakeLLMProvider
) -> None:
    claude.responders["template"] = script(drafted(BROKEN), revised(), revised())

    await generate(client)

    assert len(claude.requests) == 3
    assert (await client.get("/api/v1/usage")).json()["ai_runs"]["used"] == 1


# Confirming, renaming, reading and deleting


async def test_confirming_lists_the_template_after_the_built_ins(client: AsyncClient) -> None:
    draft = (await generate(client)).json()
    before = (await client.get("/api/v1/templates")).json()
    assert [t["id"] for t in before] == ["classic", "compact"]
    assert [t["custom"] for t in before] == [False, False]

    confirmed = await client.patch(
        f"{CUSTOM}/{draft['id']}", json={"name": "  Teal banner ", "status": "ready"}
    )

    assert confirmed.status_code == 200
    assert (confirmed.json()["name"], confirmed.json()["status"]) == ("Teal banner", "ready")
    listed = (await client.get("/api/v1/templates")).json()
    assert [t["id"] for t in listed] == ["classic", "compact", draft["id"]]
    assert listed[2] == {
        "id": draft["id"],
        "name": "Teal banner",
        "description": "Sans serif type with teal section rules and a compact header.",
        "paper_sizes": ["a4", "us-letter"],
        "target_pages": 1,
        "custom": True,
    }


async def test_rename_and_describe_a_ready_template(client: AsyncClient) -> None:
    template = await ready(client)

    response = await client.patch(
        f"{CUSTOM}/{template['id']}", json={"name": "Mine", "description": "My own."}
    )
    again = await client.patch(f"{CUSTOM}/{template['id']}", json={"status": "ready"})

    assert (response.json()["name"], response.json()["description"]) == ("Mine", "My own.")
    assert again.json()["status"] == "ready"
    listed = (await client.get("/api/v1/templates")).json()
    assert (listed[-1]["name"], listed[-1]["description"]) == ("Mine", "My own.")


@pytest.mark.parametrize(
    "body", [{"name": ""}, {"name": "x" * 61}, {"description": "x" * 201}, {"status": "draft"}]
)
async def test_updates_are_validated(client: AsyncClient, body: dict[str, Any]) -> None:
    template = await ready(client)

    response = await client.patch(f"{CUSTOM}/{template['id']}", json=body)

    assert response.status_code == 422


async def test_confirming_needs_room_under_the_limit(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    owner = await user_id(client)
    await seed(db_session, owner)
    slug = (await seed(db_session, owner, status="draft")).slug

    response = await client.patch(f"{CUSTOM}/{slug}", json={"status": "ready"})

    assert response.status_code == 402
    assert response.json()["error"]["details"]["resource"] == "templates"
    # Renaming a draft needs no room.
    assert (await client.patch(f"{CUSTOM}/{slug}", json={"name": "B"})).status_code == 200


async def test_the_source_can_be_read(client: AsyncClient) -> None:
    draft = (await generate(client)).json()

    response = await client.get(f"{CUSTOM}/{draft['id']}/source")

    assert response.status_code == 200
    assert response.json() == {"id": draft["id"], "name": "Teal rule", "main_typ": FAKE_TEMPLATE}


async def test_the_preview_renders_the_template_source(
    client: AsyncClient, renderer: FakeRendererClient, sample_content: dict[str, Any]
) -> None:
    draft = (await generate(client)).json()
    renderer.calls.clear()
    renderer.sources.clear()

    response = await client.get(f"/api/v1/templates/{draft['id']}/preview")

    assert response.status_code == 200 and response.json()["page_count"] == 1
    assert renderer.calls[-1][1] == draft["id"]
    assert renderer.calls[-1][2]["basics"]["name"] == sample_content["basics"]["name"]
    assert renderer.sources == [FAKE_TEMPLATE]
    assert renderer.source_links == [False]


async def test_deleting_a_template_removes_it(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    template = await ready(client)

    response = await client.delete(f"{CUSTOM}/{template['id']}")

    assert response.status_code == 204
    assert [t["id"] for t in (await client.get("/api/v1/templates")).json()] == [
        "classic",
        "compact",
    ]
    assert await stored(db_session) == []
    assert (await client.get(f"/api/v1/templates/{template['id']}/preview")).status_code == 404
    assert (await client.delete(f"{CUSTOM}/{template['id']}")).status_code == 404
    # The uploaded CV is kept, like an import's.
    assert len((await client.get("/api/v1/uploads")).json()) == 1


async def test_deleting_the_upload_keeps_the_template(client: AsyncClient) -> None:
    template = await ready(client)
    [upload] = (await client.get("/api/v1/uploads")).json()

    await client.delete(f"/api/v1/uploads/{upload['id']}")

    kept = await client.patch(f"{CUSTOM}/{template['id']}", json={"name": "Still here"})
    assert kept.status_code == 200 and kept.json()["upload_id"] is None


async def test_a_draft_can_be_discarded(client: AsyncClient, db_session: AsyncSession) -> None:
    draft = (await generate(client)).json()

    assert (await client.delete(f"{CUSTOM}/{draft['id']}")).status_code == 204
    assert await stored(db_session) == []


# Using it everywhere a template works


async def test_a_ready_template_works_in_every_render_path(
    client: AsyncClient, renderer: FakeRendererClient, sample_content: dict[str, Any]
) -> None:
    template = await ready(client)
    created = await profile_and_document(client, sample_content, template_id=template["id"])
    assert created.status_code == 201, created.text
    document = created.json()
    assert document["template_id"] == template["id"]
    renderer.calls.clear()
    renderer.sources.clear()
    renderer.source_links.clear()

    preview = await client.post(f"/api/v1/documents/{document['id']}/preview")
    pdf = await client.get(f"/api/v1/documents/{document['id']}/export.pdf?force=true")
    ats = await client.get(f"/api/v1/documents/{document['id']}/ats")
    fetched = await client.get(f"/api/v1/documents/{document['id']}")

    assert (preview.status_code, pdf.status_code, ats.status_code) == (200, 200, 200)
    assert fetched.json()["template_id"] == template["id"]
    assert [(fmt, tid) for fmt, tid, _ in renderer.calls] == [
        ("svg", template["id"]),
        ("pdf", template["id"]),
    ]
    assert renderer.sources == [FAKE_TEMPLATE, FAKE_TEMPLATE]
    # The editor's preview keeps its click-to-edit links.
    assert renderer.source_links == [True]


async def test_it_can_be_the_default_and_a_documents_template(
    client: AsyncClient, sample_content: dict[str, Any]
) -> None:
    template = await ready(client)

    me = await client.patch("/api/v1/me", json={"default_template_id": template["id"]})
    created = await profile_and_document(client, sample_content)
    switched = await client.patch(
        f"/api/v1/documents/{created.json()['id']}", json={"template_id": "compact"}
    )
    back = await client.patch(
        f"/api/v1/documents/{created.json()['id']}", json={"template_id": template["id"]}
    )

    assert me.json()["default_template_id"] == template["id"]
    assert created.json()["template_id"] == template["id"]
    assert (switched.json()["template_id"], back.json()["template_id"]) == (
        "compact",
        template["id"],
    )


async def test_tailoring_uses_the_template(
    client: AsyncClient, mimo: FakeLLMProvider, sample_content: dict[str, Any]
) -> None:
    template = await ready(client)
    profile = await client.post("/api/v1/profiles", json={"name": "P", "content": sample_content})

    response = await client.post(
        "/api/v1/tailor",
        json={
            "profile_id": profile.json()["id"],
            "job": {"description": "Data engineer\nAcme\nPython and SQL"},
            "template_id": template["id"],
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["document"]["template_id"] == template["id"]


async def test_the_extension_exports_a_cv_in_the_users_template(
    client: AsyncClient,
    make_client: Callable[..., AsyncClient],
    renderer: FakeRendererClient,
    sample_content: dict[str, Any],
) -> None:
    template = await ready(client)
    content = without_placeholders(sample_content)
    document = (await profile_and_document(client, content, template_id=template["id"])).json()
    connection = (await client.post("/api/v1/extension/connections", json={"label": "x"})).json()
    renderer.sources.clear()

    async with make_client(None) as extension:
        response = await extension.get(
            f"/api/v1/extension/documents/{document['id']}/cv.pdf",
            headers={"Authorization": f"Bearer {connection['token']}"},
        )

    assert response.status_code == 200, response.text
    assert renderer.sources == [FAKE_TEMPLATE]


async def test_deleting_a_template_moves_its_cvs_to_the_default(
    client: AsyncClient, sample_content: dict[str, Any], make_pro: MakePro
) -> None:
    await make_pro()
    template = await ready(client)
    await client.patch("/api/v1/me", json={"default_template_id": "compact"})
    mine = (await profile_and_document(client, sample_content, template_id=template["id"])).json()
    other = (await profile_and_document(client, sample_content, template_id="classic")).json()

    await client.delete(f"{CUSTOM}/{template['id']}")

    assert (await client.get(f"/api/v1/documents/{mine['id']}")).json()["template_id"] == "compact"
    assert (await client.get(f"/api/v1/documents/{other['id']}")).json()["template_id"] == "classic"
    assert (await client.get("/api/v1/me")).json()["default_template_id"] == "compact"


async def test_deleting_the_default_template_falls_back_to_classic(
    client: AsyncClient, sample_content: dict[str, Any]
) -> None:
    template = await ready(client)
    await client.patch("/api/v1/me", json={"default_template_id": template["id"]})
    mine = (await profile_and_document(client, sample_content)).json()
    assert mine["template_id"] == template["id"]

    await client.delete(f"{CUSTOM}/{template['id']}")

    assert (await client.get(f"/api/v1/documents/{mine['id']}")).json()["template_id"] == "classic"
    assert (await client.get("/api/v1/me")).json()["default_template_id"] == "classic"
    # And the preview still works, with the built-in template.
    assert (await client.post(f"/api/v1/documents/{mine['id']}/preview")).status_code == 200


async def test_deleting_falls_back_to_classic_when_the_default_no_longer_exists(
    client: AsyncClient, sample_content: dict[str, Any], db_session: AsyncSession
) -> None:
    template = await ready(client)
    mine = (await profile_and_document(client, sample_content, template_id=template["id"])).json()
    await db_session.execute(update(User).values(default_template_id="retired"))

    await client.delete(f"{CUSTOM}/{template['id']}")

    assert (await client.get(f"/api/v1/documents/{mine['id']}")).json()["template_id"] == "classic"


async def test_deleting_moves_its_cvs_to_a_custom_default(
    client: AsyncClient, sample_content: dict[str, Any], make_pro: MakePro
) -> None:
    await make_pro()
    first, second = await ready(client), await ready(client)
    await client.patch("/api/v1/me", json={"default_template_id": second["id"]})
    mine = (await profile_and_document(client, sample_content, template_id=first["id"])).json()

    await client.delete(f"{CUSTOM}/{first['id']}")

    moved = (await client.get(f"/api/v1/documents/{mine['id']}")).json()
    assert moved["template_id"] == second["id"]


# Another user's templates


async def test_another_users_template_is_not_found_anywhere(
    client: AsyncClient,
    other_client: AsyncClient,
    sample_content: dict[str, Any],
    renderer: FakeRendererClient,
) -> None:
    template = await ready(client)
    slug = template["id"]
    document = (await profile_and_document(other_client, sample_content)).json()
    profile = (
        await other_client.post("/api/v1/profiles", json={"name": "P", "content": sample_content})
    ).json()
    renderer.calls.clear()

    responses = {
        "preview": await other_client.get(f"/api/v1/templates/{slug}/preview"),
        "source": await other_client.get(f"{CUSTOM}/{slug}/source"),
        "patch": await other_client.patch(f"{CUSTOM}/{slug}", json={"name": "Mine now"}),
        "confirm": await other_client.patch(f"{CUSTOM}/{slug}", json={"status": "ready"}),
        "delete": await other_client.delete(f"{CUSTOM}/{slug}"),
        "create document": await other_client.post(
            "/api/v1/documents", json={"profile_id": profile["id"], "template_id": slug}
        ),
        "switch document": await other_client.patch(
            f"/api/v1/documents/{document['id']}", json={"template_id": slug}
        ),
        "default": await other_client.patch("/api/v1/me", json={"default_template_id": slug}),
        "tailor": await other_client.post(
            "/api/v1/tailor",
            json={
                "profile_id": profile["id"],
                "job": {"description": "Data engineer"},
                "template_id": slug,
            },
        ),
    }

    assert {name: r.status_code for name, r in responses.items()} == dict.fromkeys(responses, 404)
    for response in responses.values():
        assert response.json()["error"]["code"] == "not_found"
    assert renderer.calls == []
    assert [t["id"] for t in (await other_client.get("/api/v1/templates")).json()] == [
        "classic",
        "compact",
    ]
    # Nothing of theirs changed.
    assert (await client.get(f"{CUSTOM}/{slug}/source")).status_code == 200
    assert (await client.get("/api/v1/templates")).json()[-1]["name"] == "Teal rule"
    assert (await other_client.get("/api/v1/me")).json()["default_template_id"] is None


async def test_a_draft_is_not_usable_before_it_is_confirmed(
    client: AsyncClient, sample_content: dict[str, Any]
) -> None:
    draft = (await generate(client)).json()
    profile = (
        await client.post("/api/v1/profiles", json={"name": "P", "content": sample_content})
    ).json()

    created = await client.post(
        "/api/v1/documents", json={"profile_id": profile["id"], "template_id": draft["id"]}
    )
    default = await client.patch("/api/v1/me", json={"default_template_id": draft["id"]})

    assert (created.status_code, default.status_code) == (404, 404)
    assert [t["id"] for t in (await client.get("/api/v1/templates")).json()] == [
        "classic",
        "compact",
    ]


async def test_an_unknown_template_id_is_a_404_when_it_looks_like_a_custom_one(
    client: AsyncClient,
) -> None:
    unknown = await client.get("/api/v1/templates/u-abcdefghij/preview")
    built_in = await client.get("/api/v1/templates/fancy/preview")

    assert (unknown.status_code, built_in.status_code) == (404, 422)


async def test_the_fake_model_answers_with_the_fixture_template() -> None:
    assert (FIXTURES / "user-template.typ").read_text() == FAKE_TEMPLATE


async def test_stored_rows_belong_to_their_owner(
    client: AsyncClient, other_client: AsyncClient, db_session: AsyncSession
) -> None:
    await generate(client)
    mine = await user_id(client)

    [row] = await stored(db_session)

    assert row.user_id == mine
    assert (await db_session.scalar(select(Upload.user_id))) == mine
