"""POST /extension/answers with the fake providers: drafted answers to application questions.

Drafts follow their own rule (docs/PRODUCT.md, 8, Answer questions): no fact guard, nothing saved,
one AI run per request."""

import logging
import uuid
from collections.abc import AsyncIterator, Callable
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.ai.prompts import draft_answers as answers_prompt
from api.db.models import AiRun, Document, DocumentVersion, Job, Profile
from api.ports.llm.base import LLMRequest, ProviderName, provider_failure
from api.ports.llm.fake import FakeLLMProvider
from cvcore.ai import DraftAnswer, DraftAnswers, JobAnalysis, SkillMention

QUESTION = {"id": "f1", "text": "Describe a time you used Databricks in production."}
FAKE_DRAFT = (
    "At Northwind Consulting I worked as lead data engineer with Python and Spark, and moved "
    "[[how many]] jobs to Databricks."
)


async def connect(client: AsyncClient) -> str:
    response = await client.post("/api/v1/extension/connections", json={"label": "Chrome"})
    assert response.status_code == 201, response.text
    return response.json()["token"]


@pytest.fixture
def make_extension(make_client: Callable[..., AsyncClient]) -> Callable[[str], AsyncClient]:
    def make(token: str) -> AsyncClient:
        client = make_client(None)
        client.headers["Authorization"] = f"Bearer {token}"
        return client

    return make


@pytest.fixture
async def extension(
    client: AsyncClient, make_extension: Callable[[str], AsyncClient]
) -> AsyncIterator[AsyncClient]:
    async with make_extension(await connect(client)) as c:
        yield c


async def make_profile(client: AsyncClient, content: dict[str, Any]) -> str:
    response = await client.post("/api/v1/profiles", json={"name": "Data", "content": content})
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def draft(extension: AsyncClient, source: dict[str, str], **body: Any) -> Response:
    body.setdefault("questions", [QUESTION])
    return await extension.post("/api/v1/extension/answers", json={"source": source, **body})


def answering(*answers: DraftAnswer) -> Any:
    def respond(_: LLMRequest[Any]) -> DraftAnswers:
        return DraftAnswers(answers=list(answers))

    return respond


async def runs(db_session: AsyncSession) -> list[tuple[str, str, str]]:
    rows = (await db_session.scalars(select(AiRun).order_by(AiRun.created_at))).all()
    return [(r.task, r.provider, r.status) for r in rows]


async def counts(db_session: AsyncSession) -> list[int]:
    tables = (Profile, Document, DocumentVersion, Job)
    return [(await db_session.scalar(select(func.count()).select_from(t))) or 0 for t in tables]


async def test_drafts_one_answer_per_question_in_one_run(
    client: AsyncClient,
    extension: AsyncClient,
    sample_content: dict[str, Any],
    mimo: FakeLLMProvider,
    db_session: AsyncSession,
) -> None:
    profile_id = await make_profile(client, sample_content)
    before = await counts(db_session)
    questions = [
        QUESTION,
        {"id": "f2", "text": "Why do you want to work here?", "multiline": False},
        {"id": "f3", "text": "In 10 words, your best project?", "max_words": 10},
    ]

    response = await draft(extension, {"kind": "profile", "id": profile_id}, questions=questions)

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["ai_model"], body["ai_model_label"], body["model"]) == (
        "mimo-flash",
        "MiMo Flash",
        "mimo-v2.6-flash",
    )
    assert [a["id"] for a in body["answers"]] == ["f1", "f2", "f3"]
    assert body["answers"][0] == {
        "id": "f1",
        "text": FAKE_DRAFT,
        "inferred": [{"skill": "Databricks", "based_on": ["Python", "Spark"]}],
        "placeholders": 1,
        "shortened": False,
    }
    third = body["answers"][2]
    assert third["text"] == "At Northwind Consulting I worked as lead data engineer with"
    assert third["shortened"] is True
    # One request is one AI run, whatever the number of questions; nothing else is written.
    assert len(mimo.requests) == 1
    assert await runs(db_session) == [("answers", "mimo", "succeeded")]
    assert await counts(db_session) == before


async def test_the_prompt_has_the_material_without_contact_details(
    client: AsyncClient,
    extension: AsyncClient,
    sample_content: dict[str, Any],
    mimo: FakeLLMProvider,
) -> None:
    profile_id = await make_profile(client, sample_content)
    question = {**QUESTION, "multiline": False, "max_words": 50, "previous": "Old draft"}

    await draft(extension, {"kind": "profile", "id": profile_id}, questions=[question])

    request = mimo.requests[-1]
    assert (request.task, request.effort) == ("answers", "low")
    profile = answers_prompt.profile_from(request.user_text)
    assert profile.basics.name == "Ama Owusu-Mensah"
    assert (profile.basics.email, profile.basics.phone, profile.basics.links) == ("", "", [])
    assert "ama@example.com" not in request.user_text
    assert answers_prompt.questions_from(request.user_text) == [
        answers_prompt.Question(
            id="f1",
            text=QUESTION["text"],
            single_line=True,
            max_words=50,
            max_chars=None,
            previous="Old draft",
        )
    ]
    assert "There is no job advertisement." in request.user_text


async def test_a_saved_job_gives_the_ad_its_analysis_and_keywords(
    client: AsyncClient,
    extension: AsyncClient,
    sample_content: dict[str, Any],
    mimo: FakeLLMProvider,
    db_session: AsyncSession,
) -> None:
    profile_id = await make_profile(client, sample_content)
    job = await client.post(
        "/api/v1/jobs",
        json={"description": "Build pipelines with Looker.", "title": "Data engineer"},
    )
    analysis = JobAnalysis(
        title="Data engineer",
        company="Harbour Bank",
        seniority="senior",
        must_have=["Looker"],
        nice_to_have=[],
        keywords=["Spark"],
        summary="",
    )
    row = await db_session.get(Job, uuid.UUID(job.json()["id"]))
    assert row is not None
    row.analysis = analysis.model_dump()
    await db_session.commit()
    mimo.responders["answers"] = answering(
        DraftAnswer(id="f1", text="I built Looker dashboards on Spark.", skills=[])
    )

    response = await draft(
        extension,
        {"kind": "profile", "id": profile_id},
        job_id=job.json()["id"],
        job={"description": "Ignored, the saved job wins."},
    )

    sent = mimo.requests[-1].user_text
    assert "Title: Data engineer\n\nBuild pipelines with Looker." in sent
    assert "<job_analysis>" in sent
    assert "Ignored" not in sent
    # The model did not report Looker; the job's keywords catch it. Spark is in the profile.
    assert response.json()["answers"][0]["inferred"] == [{"skill": "Looker", "based_on": []}]


async def test_an_ad_from_the_page_is_used_and_not_saved(
    client: AsyncClient,
    extension: AsyncClient,
    sample_content: dict[str, Any],
    mimo: FakeLLMProvider,
    db_session: AsyncSession,
) -> None:
    profile_id = await make_profile(client, sample_content)
    page_ad = {"description": "We run 40 pipelines.", "title": "Analyst", "company": "Acme"}
    mimo.responders["answers"] = answering(
        DraftAnswer(id="f1", text="I would own 40 pipelines and cut 25% of costs.", skills=[])
    )

    response = await draft(extension, {"kind": "profile", "id": profile_id}, job=page_ad)

    assert "Title: Analyst\nCompany: Acme\n\nWe run 40 pipelines." in mimo.requests[-1].user_text
    # 40 is in the ad; 25% is in neither the ad, the question nor the profile.
    assert response.json()["answers"][0]["text"] == (
        "I would own 40 pipelines and cut [[check this number: 25%]] of costs."
    )
    assert (await db_session.scalar(select(func.count()).select_from(Job))) == 0


async def test_a_cv_can_be_the_source_and_missing_answers_are_empty(
    client: AsyncClient,
    extension: AsyncClient,
    sample_content: dict[str, Any],
    mimo: FakeLLMProvider,
) -> None:
    profile_id = await make_profile(client, sample_content)
    cv = await client.post("/api/v1/documents", json={"profile_id": profile_id})
    mimo.responders["answers"] = answering(
        DraftAnswer(id="f2", text="Second.", skills=[SkillMention(skill="Kafka", based_on=[])]),
        DraftAnswer(id="unknown", text="Not asked.", skills=[]),
    )
    questions = [QUESTION, {"id": "f2", "text": "What else?"}]

    response = await draft(
        extension, {"kind": "document", "id": cv.json()["id"]}, questions=questions
    )

    assert [(a["id"], a["text"], a["inferred"]) for a in response.json()["answers"]] == [
        ("f1", "", []),
        ("f2", "Second.", []),  # Kafka is named only by the model, not in the answer
    ]


async def test_invalid_requests_call_no_model(
    client: AsyncClient,
    extension: AsyncClient,
    sample_content: dict[str, Any],
    mimo: FakeLLMProvider,
    db_session: AsyncSession,
) -> None:
    profile_id = await make_profile(client, sample_content)
    source = {"kind": "profile", "id": profile_id}

    replies = [
        await draft(extension, source, questions=[]),
        await draft(extension, source, questions=[QUESTION] * 2),
        await draft(
            extension, source, questions=[{"id": f"f{n}", "text": "Why?"} for n in range(21)]
        ),
        await draft(extension, source, questions=[{"id": "f1", "text": "   "}]),
        await draft(extension, source, questions=[{**QUESTION, "max_words": 0}]),
        await draft(extension, {"kind": "upload", "id": profile_id}),
        await draft(extension, source, job={"description": ""}),
    ]

    assert [r.status_code for r in replies] == [422] * 7
    assert replies[1].json()["error"]["message"] == (
        "Check questions: Value error, each question needs its own id"
    )
    assert QUESTION["text"] not in replies[1].text, "values are never echoed"
    assert mimo.requests == []
    assert await runs(db_session) == []


async def test_only_the_tokens_own_data(
    client: AsyncClient,
    other_client: AsyncClient,
    extension: AsyncClient,
    sample_content: dict[str, Any],
    mimo: FakeLLMProvider,
    db_session: AsyncSession,
) -> None:
    theirs = await make_profile(other_client, sample_content)
    their_cv = await other_client.post("/api/v1/documents", json={"profile_id": theirs})
    their_job = await other_client.post("/api/v1/jobs", json={"description": "Their ad"})
    mine = await make_profile(client, sample_content)

    replies = [
        await draft(extension, {"kind": "profile", "id": theirs}),
        await draft(extension, {"kind": "document", "id": their_cv.json()["id"]}),
        await draft(extension, {"kind": "profile", "id": mine}, job_id=their_job.json()["id"]),
    ]

    assert [r.status_code for r in replies] == [404, 404, 404]
    assert mimo.requests == []
    assert await runs(db_session) == []


async def test_the_route_takes_the_extension_token_only(
    client: AsyncClient,
    make_extension: Callable[[str], AsyncClient],
    sample_content: dict[str, Any],
    mimo: FakeLLMProvider,
) -> None:
    profile_id = await make_profile(client, sample_content)
    source = {"kind": "profile", "id": profile_id}
    token = await connect(client)

    signed_in = await client.post(
        "/api/v1/extension/answers", json={"source": source, "questions": [QUESTION]}
    )
    async with make_extension(token) as extension:
        await extension.delete("/api/v1/extension/session")
        revoked = await draft(extension, source)

    assert (signed_in.status_code, revoked.status_code) == (401, 401)
    assert mimo.requests == []


async def test_plan_limits_apply_before_any_model_call(
    client: AsyncClient,
    extension: AsyncClient,
    sample_content: dict[str, Any],
    mimo: FakeLLMProvider,
    claude: FakeLLMProvider,
    db_session: AsyncSession,
) -> None:
    profile_id = await make_profile(client, sample_content)
    source = {"kind": "profile", "id": profile_id}

    pro_model = await draft(extension, source, ai_model="claude-sonnet")
    owner = uuid.UUID((await client.get("/api/v1/me")).json()["id"])
    db_session.add_all(
        AiRun(
            user_id=owner,
            task="answers",
            provider="mimo",
            model="mimo-v2.6-flash",
            prompt_version="1",
            status="failed",
        )
        for _ in range(20)
    )
    await db_session.commit()
    spent = await draft(extension, source)

    assert pro_model.status_code == 402
    assert pro_model.json()["error"]["code"] == "plan_required"
    # On Free, failed runs count too.
    assert spent.status_code == 402
    assert spent.json()["error"]["details"]["resource"] == "ai_runs"
    assert spent.json()["error"]["message"].startswith("You have used all of this month's AI")
    assert (mimo.requests, claude.requests) == ([], [])


async def test_pro_users_can_choose_a_pro_model(
    client: AsyncClient,
    extension: AsyncClient,
    sample_content: dict[str, Any],
    claude: FakeLLMProvider,
    make_pro: Callable[..., Any],
) -> None:
    profile_id = await make_profile(client, sample_content)
    await make_pro()

    response = await draft(
        extension, {"kind": "profile", "id": profile_id}, ai_model="claude-sonnet"
    )

    assert response.status_code == 200, response.text
    assert response.json()["ai_model"] == "claude-sonnet"
    assert len(claude.requests) == 1


async def test_a_failed_draft_is_recorded(
    client: AsyncClient,
    extension: AsyncClient,
    sample_content: dict[str, Any],
    mimo: FakeLLMProvider,
    db_session: AsyncSession,
) -> None:
    profile_id = await make_profile(client, sample_content)
    mimo.fail_with = provider_failure(ProviderName.mimo, "invalid_output")

    response = await draft(extension, {"kind": "profile", "id": profile_id})

    assert response.status_code == 502
    assert await runs(db_session) == [("answers", "mimo", "failed")]


async def test_no_question_ad_draft_or_prompt_is_logged(
    client: AsyncClient,
    extension: AsyncClient,
    sample_content: dict[str, Any],
    mimo: FakeLLMProvider,
    caplog: pytest.LogCaptureFixture,
) -> None:
    profile_id = await make_profile(client, sample_content)
    source = {"kind": "profile", "id": profile_id}
    question = {"id": "f1", "text": "Describe your secret hobby of collecting teapots."}
    page_ad = {"description": "Harbour Bank wants a teapot-loving analyst.", "title": "Analyst"}
    secrets = ["teapot", "Harbour Bank", "Northwind", "[[how many]]", "Databricks"]

    with caplog.at_level(logging.DEBUG):
        ok = await draft(extension, source, questions=[question], job=page_ad)
        mimo.fail_with = provider_failure(ProviderName.mimo, "invalid_output")
        failed = await draft(extension, source, questions=[question], job=page_ad)

    assert (ok.status_code, failed.status_code) == (200, 502)
    assert caplog.records, "the runs are logged"
    logged = " ".join(
        [record.getMessage() + " " + str(record.__dict__) for record in caplog.records]
    )
    assert [secret for secret in secrets if secret in logged] == []
