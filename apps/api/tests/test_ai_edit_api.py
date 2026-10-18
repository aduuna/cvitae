"""POST /documents/{id}/ai-edit with the fake providers: a change asked for in words."""

import uuid
from collections.abc import Callable
from typing import Any

from httpx import AsyncClient, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.ai.prompts import edit_cv as edit_prompt
from api.db.models import AiRun, Document
from api.ports.llm.base import LLMRequest, ProviderName, provider_failure
from api.ports.llm.fake import FakeLLMProvider
from cvcore.models import Bullet, CvContent
from cvcore.render import iter_bullets
from cvcore.wire import WireCvEdit, to_wire


async def new_cv(client: AsyncClient, content: dict[str, Any]) -> dict[str, Any]:
    profile = await client.post("/api/v1/profiles", json={"name": "Data", "content": content})
    created = await client.post("/api/v1/documents", json={"profile_id": profile.json()["id"]})
    assert created.status_code == 201, created.text
    return created.json()


async def ai_edit(client: AsyncClient, document_id: str, message: str, **body: Any) -> Response:
    return await client.post(
        f"/api/v1/documents/{document_id}/ai-edit", json={"message": message, **body}
    )


def editing(change: Callable[[CvContent], None], reply: str = "Done.") -> Any:
    """A responder that applies `change` to the CV it is given."""

    def respond(request: LLMRequest[Any]) -> WireCvEdit:
        cv = edit_prompt.cv_from(request.user_text)
        change(cv)
        return WireCvEdit(reply=reply, content=to_wire(cv))

    return respond


def bullet(content: CvContent, bullet_id: str) -> Bullet:
    return next(b for b in iter_bullets(content) if b.id == bullet_id)


def section(content: CvContent, section_id: str) -> Any:
    return next(s for s in content.sections if s.id == section_id)


async def runs(db_session: AsyncSession) -> list[tuple[str, str, str]]:
    rows = (await db_session.scalars(select(AiRun).order_by(AiRun.created_at))).all()
    return [(r.task, r.provider, r.status) for r in rows]


async def test_an_edit_returns_the_changed_cv_without_saving_it(
    client: AsyncClient,
    sample_content: dict[str, Any],
    mimo: FakeLLMProvider,
    db_session: AsyncSession,
) -> None:
    doc = await new_cv(client, sample_content)

    def shorten(cv: CvContent) -> None:
        cv.summary = "Data engineer with **9 years** of experience."
        bullet(cv, "b-bl-1").text = "Built the first warehouse on BigQuery."

    mimo.responders["edit"] = editing(shorten, reply="  Shortened the summary to **9 years**.  ")

    response = await ai_edit(client, doc["id"], "  Shorten the summary  ")

    assert response.status_code == 200, response.text
    result = response.json()
    assert (result["reply"], result["changed"], result["issues"]) == (
        "Shortened the summary to 9 years.",
        True,
        [],
    )
    assert (result["ai_model"], result["model"]) == ("mimo-flash", "mimo-v2.6-flash")
    content = CvContent.model_validate(result["content"])
    assert content.summary == "Data engineer with **9 years** of experience."
    assert bullet(content, "b-bl-1").text == "Built the first warehouse on BigQuery."

    # Nothing is saved; the content before the edit is kept as a version.
    saved = (await client.get(f"/api/v1/documents/{doc['id']}")).json()
    assert saved["content"] == doc["content"]
    versions = (await client.get(f"/api/v1/documents/{doc['id']}/versions")).json()
    assert [v["reason"] for v in versions] == ["autosave"]
    assert await runs(db_session) == [("edit", "mimo", "succeeded")]

    request = mimo.requests[-1]
    assert request.task == "edit"
    assert request.user_text.endswith("<request>\nShorten the summary\n</request>")
    assert "The request may change any part of the CV." in request.user_text


async def test_the_fact_guard_checks_edits_against_the_cv(
    client: AsyncClient, sample_content: dict[str, Any], mimo: FakeLLMProvider
) -> None:
    doc = await new_cv(client, sample_content)

    def invent(cv: CvContent) -> None:
        bullet(cv, "b-bl-3").text = "Mentored 4 graduate engineers through their first year."
        role = next(i for s in cv.sections for i in s.experience if i.id == "exp-brightline")
        role.role = "Head of data"
        role.bullets.append(Bullet(id="new-1", text="Won the company award."))

    mimo.responders["edit"] = editing(invent)

    result = (await ai_edit(client, doc["id"], "Make my Brightline role stronger")).json()

    assert [(i["kind"], i["value"]) for i in result["issues"]] == [
        ("changed_fact", "Head of data"),
        ("new_number", "4"),
        ("new_claim", "Won the company award."),
    ]
    assert result["issues"][0]["message"] == "Kept the role from your CV."
    content = CvContent.model_validate(result["content"])
    role = next(i for s in content.sections for i in s.experience if i.id == "exp-brightline")
    assert role.role == "Data engineer"
    assert "[[check this number: 4]]" in bullet(content, "b-bl-3").text
    assert bullet(content, "new-1").text == "[[Won the company award.]]"


async def test_bullets_keep_their_links_to_the_profile(
    client: AsyncClient, sample_content: dict[str, Any], mimo: FakeLLMProvider
) -> None:
    doc = await new_cv(client, sample_content)
    content = CvContent.model_validate(doc["content"])
    for item in iter_bullets(content):
        item.source_id = f"profile-{item.id}"
    linked = content.model_dump(mode="json")
    await client.patch(f"/api/v1/documents/{doc['id']}", json={"content": linked})

    def reword(cv: CvContent) -> None:
        bullet(cv, "b-bl-1").text = "Built the first warehouse on BigQuery."

    mimo.responders["edit"] = editing(reword)

    result = (await ai_edit(client, doc["id"], "Shorten the first Brightline bullet")).json()

    edited = CvContent.model_validate(result["content"])
    assert {b.id: b.source_id for b in iter_bullets(edited)} == {
        b.id: f"profile-{b.id}" for b in iter_bullets(content)
    }
    # The model sees this CV's own bullets, not the profile's ids.
    assert "profile-" not in mimo.requests[-1].user_text


async def test_a_scope_limits_what_can_change(
    client: AsyncClient, sample_content: dict[str, Any], mimo: FakeLLMProvider
) -> None:
    doc = await new_cv(client, sample_content)
    original = CvContent.model_validate(doc["content"])

    def everything(cv: CvContent) -> None:
        cv.summary = "Data engineer."
        section(cv, "sec-skills").title = "Tools"
        cv.sections = [s for s in cv.sections if s.id != "sec-lang"]

    mimo.responders["edit"] = editing(everything)

    summary = (await ai_edit(client, doc["id"], "Tighten this", scope="summary")).json()
    skills = (await ai_edit(client, doc["id"], "Rename it", scope="sec-skills")).json()
    removed = (await ai_edit(client, doc["id"], "Drop it", scope="sec-lang")).json()

    only_summary = CvContent.model_validate(summary["content"])
    assert only_summary.summary == "Data engineer."
    assert only_summary.sections == original.sections

    only_skills = CvContent.model_validate(skills["content"])
    assert only_skills.summary == original.summary
    assert section(only_skills, "sec-skills").title == "Tools"
    assert [s.id for s in only_skills.sections] == [s.id for s in original.sections]

    without = CvContent.model_validate(removed["content"])
    assert [s.id for s in without.sections] == [
        s.id for s in original.sections if s.id != "sec-lang"
    ]
    assert section(without, "sec-skills").title == "Skills"

    assert 'Change only the section titled "Skills" (id sec-skills)' in (mimo.requests[1].user_text)
    assert "Change only the summary" in mimo.requests[0].user_text


async def test_a_question_changes_nothing_and_sees_the_conversation(
    client: AsyncClient,
    sample_content: dict[str, Any],
    mimo: FakeLLMProvider,
    db_session: AsyncSession,
) -> None:
    doc = await new_cv(client, sample_content)

    response = await ai_edit(
        client,
        doc["id"],
        "Which role is strongest?",
        history=[
            {"role": "user", "text": "Shorten the summary"},
            {"role": "assistant", "text": "Shortened the summary."},
        ],
        ai_model="gemini-flash-lite",
    )

    result = response.json()
    assert (result["changed"], result["reply"], result["ai_model"]) == (
        False,
        "I made no change.",
        "gemini-flash-lite",
    )
    assert result["content"] == doc["content"]
    assert (await client.get(f"/api/v1/documents/{doc['id']}/versions")).json() == []
    assert mimo.requests == []
    assert await runs(db_session) == [("edit", "gemini", "succeeded")]


async def test_the_conversation_is_sent_before_the_cv(
    client: AsyncClient, sample_content: dict[str, Any], mimo: FakeLLMProvider
) -> None:
    doc = await new_cv(client, sample_content)

    await ai_edit(
        client,
        doc["id"],
        "Shorter still",
        history=[
            {"role": "user", "text": "Shorten the summary"},
            {"role": "assistant", "text": "Shortened the summary."},
        ],
    )

    text = mimo.requests[-1].user_text
    assert text.startswith(
        "<conversation>\nPerson: Shorten the summary\nYou: Shortened the summary.\n"
        "</conversation>\n\n<cv>\n"
    )


async def test_requests_that_cannot_run_call_no_model(
    client: AsyncClient,
    other_client: AsyncClient,
    sample_content: dict[str, Any],
    mimo: FakeLLMProvider,
    db_session: AsyncSession,
) -> None:
    doc = await new_cv(client, sample_content)
    ejected = await new_cv(client, sample_content)
    await db_session.execute(
        update(Document).where(Document.id == uuid.UUID(ejected["id"])).values(mode="ejected")
    )
    # Committed, so the refused requests' rollbacks keep it.
    await db_session.commit()

    blank = await ai_edit(client, doc["id"], "   ")
    long_history = await ai_edit(
        client, doc["id"], "Shorter", history=[{"role": "user", "text": "Hi"}] * 13
    )
    gone = await ai_edit(client, doc["id"], "Shorter", scope="sec-gone")
    typst = await ai_edit(client, ejected["id"], "Shorter")
    someone_elses = await ai_edit(other_client, doc["id"], "Shorter")
    pro_model = await ai_edit(client, doc["id"], "Shorter", ai_model="claude-sonnet")

    assert (blank.status_code, long_history.status_code) == (422, 422)
    assert gone.status_code == 422
    assert gone.json()["error"]["message"] == (
        "That section is no longer in this CV. Choose another part to change."
    )
    assert typst.status_code == 409
    assert someone_elses.status_code == 404
    assert pro_model.json()["error"]["code"] == "plan_required"
    assert mimo.requests == []
    assert await runs(db_session) == []


async def test_no_ai_usage_left_means_no_model_call(
    client: AsyncClient,
    sample_content: dict[str, Any],
    mimo: FakeLLMProvider,
    db_session: AsyncSession,
) -> None:
    doc = await new_cv(client, sample_content)
    owner = uuid.UUID((await client.get("/api/v1/me")).json()["id"])
    db_session.add_all(
        AiRun(
            user_id=owner,
            task="edit",
            provider="mimo",
            model="mimo-v2.6-flash",
            prompt_version="1",
            status="failed",
        )
        for _ in range(20)
    )
    await db_session.commit()

    response = await ai_edit(client, doc["id"], "Shorter")

    # On Free, failed runs count too.
    assert response.status_code == 402
    assert response.json()["error"]["details"]["resource"] == "ai_runs"
    assert mimo.requests == []


async def test_a_failed_edit_is_recorded_and_keeps_no_version(
    client: AsyncClient,
    sample_content: dict[str, Any],
    mimo: FakeLLMProvider,
    db_session: AsyncSession,
) -> None:
    doc = await new_cv(client, sample_content)
    mimo.fail_with = provider_failure(ProviderName.mimo, "invalid_output")

    response = await ai_edit(client, doc["id"], "Shorter")

    assert response.status_code == 502
    assert response.json()["error"]["message"] == (
        "MiMo returned something we could not read. Try again."
    )
    assert await runs(db_session) == [("edit", "mimo", "failed")]
    assert (await client.get(f"/api/v1/documents/{doc['id']}/versions")).json() == []


async def test_a_section_whose_kind_changed_is_kept_as_it_was(
    client: AsyncClient, sample_content: dict[str, Any], mimo: FakeLLMProvider
) -> None:
    doc = await new_cv(client, sample_content)

    def retype(cv: CvContent) -> None:
        section(cv, "sec-lang").kind = "skills"

    mimo.responders["edit"] = editing(retype)

    result = (await ai_edit(client, doc["id"], "Make it a skills list", scope="sec-lang")).json()

    assert result["changed"] is False
    assert result["content"] == doc["content"]
