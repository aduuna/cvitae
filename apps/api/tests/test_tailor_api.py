"""POST /tailor with the fake providers: the M3 tailoring flow end to end."""

from pathlib import Path
from typing import Any

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import AiRun
from api.ports.llm.base import LLMRequest
from api.ports.llm.fake import FakeLLMProvider, default_responders
from cvcore.factguard import number_tokens
from cvcore.models import CvContent
from cvcore.render import iter_bullets
from cvcore.richtext import plain_text
from cvcore.wire import WireChange, WireTailoredCv, from_wire, to_wire

FIXTURES = Path(__file__).resolve().parents[3] / "templates" / "fixtures"

JOB_AD = (FIXTURES / "job-data-engineer.txt").read_text()


async def make_profile(client: AsyncClient, content: dict[str, Any]) -> str:
    response = await client.post("/api/v1/profiles", json={"name": "Data", "content": content})
    return response.json()["id"]


async def tailor(client: AsyncClient, **body: Any) -> Any:
    return await client.post("/api/v1/tailor", json=body)


async def test_tailoring_flow_end_to_end(
    client: AsyncClient,
    sample_content: dict[str, Any],
    mimo: FakeLLMProvider,
    gemini: FakeLLMProvider,
    db_session: AsyncSession,
) -> None:
    profile_id = await make_profile(client, sample_content)

    response = await tailor(
        client,
        profile_id=profile_id,
        job={"description": JOB_AD},
        template_id="compact",
    )

    assert response.status_code == 201
    result = response.json()
    document, job = result["document"], result["job"]
    assert (result["ai_model"], result["provider"], result["model"]) == (
        "mimo-flash",
        "mimo",
        "mimo-v2.6-flash",
    )
    # The analysis filled in the title and company the user left out.
    assert job["title"] == "Senior Data Engineer, Payments Platform"
    assert job["company"].startswith("Lumen Payments")
    assert document["name"] == f"{job['title']} at {job['company']}"
    assert (document["template_id"], document["job_id"], document["profile_id"]) == (
        "compact",
        job["id"],
        profile_id,
    )

    # Every bullet traces to a source bullet, and no number is new.
    source = CvContent.model_validate(sample_content)
    originals = {b.id: b for b in iter_bullets(source)}
    tailored = CvContent.model_validate(document["content"])
    for bullet in iter_bullets(tailored):
        assert bullet.source_id in originals
        source_numbers = number_tokens(plain_text(originals[bullet.source_id].text))
        assert number_tokens(plain_text(bullet.text)) <= source_numbers
    assert result["issues"] == []
    assert {c["source_id"] for c in result["changes"]} == set(originals)
    assert result["dropped"] == []
    assert [p["text"] for p in result["placeholders"]] == ["number of analysts"]
    assert result["missing_keywords"] == ["Snowflake", "Kubernetes"]

    # A tailor version exists, and two AI runs were recorded.
    versions = (await client.get(f"/api/v1/documents/{document['id']}/versions")).json()
    assert [v["reason"] for v in versions] == ["tailor"]
    runs = (await db_session.scalars(select(AiRun).order_by(AiRun.created_at))).all()
    assert [(r.task, r.provider, r.status) for r in runs] == [
        ("analyze_job", "mimo", "succeeded"),
        ("tailor", "mimo", "succeeded"),
    ]

    # Regenerate with the other provider: discard the draft CV, tailor the saved job again.
    assert (await client.delete(f"/api/v1/documents/{document['id']}")).status_code == 204
    again = await tailor(client, profile_id=profile_id, job_id=job["id"], ai_model="gemini-flash")

    assert again.status_code == 201
    assert (again.json()["ai_model"], again.json()["model"]) == ("gemini-flash", "gemini-3.8-flash")
    # The job's analysis is kept, so only the tailoring ran again.
    assert [r.task for r in gemini.requests] == ["tailor"]
    assert len((await client.get("/api/v1/documents")).json()) == 1


async def test_the_fact_guard_corrects_what_the_model_invents(
    client: AsyncClient,
    sample_content: dict[str, Any],
    mimo: FakeLLMProvider,
    sample_profile: CvContent,
) -> None:
    faithful = default_responders(sample_profile)["tailor"]

    def inventive(request: LLMRequest[Any]) -> WireTailoredCv:
        result = WireTailoredCv.model_validate(faithful(request).model_dump())
        content = from_wire(result.content)
        first = next(iter_bullets(content))
        first.text = "Lead a team of **5 engineers** across 40 banks."
        content.basics.name = "Someone Else"
        result.content = to_wire(content)
        return result

    mimo.responders["tailor"] = inventive
    profile_id = await make_profile(client, sample_content)

    result = (await tailor(client, profile_id=profile_id, job={"description": JOB_AD})).json()

    assert [(i["kind"], i["value"]) for i in result["issues"]] == [
        ("changed_fact", "Someone Else"),
        ("new_number", "40"),
    ]
    content = CvContent.model_validate(result["document"]["content"])
    assert content.basics.name == sample_content["basics"]["name"]
    assert "[[check this number: 40]]" in next(iter_bullets(content)).text
    assert "check this number: 40" in [p["text"] for p in result["placeholders"]]


async def test_dropped_bullets_and_rationales_are_reported(
    client: AsyncClient,
    sample_content: dict[str, Any],
    mimo: FakeLLMProvider,
    sample_profile: CvContent,
) -> None:
    faithful = default_responders(sample_profile)["tailor"]

    def selective(request: LLMRequest[Any]) -> WireTailoredCv:
        result = WireTailoredCv.model_validate(faithful(request).model_dump())
        content = from_wire(result.content)
        for section in content.sections:
            for item in section.experience:
                if item.org == "Kente Labs":
                    item.bullets = []
        first = next(iter_bullets(content))
        result.content = to_wire(content)
        result.changes = [
            WireChange(source_id=first.source_id or "", rationale="Leads with team size.")
        ]
        return result

    mimo.responders["tailor"] = selective
    profile_id = await make_profile(client, sample_content)

    result = (await tailor(client, profile_id=profile_id, job={"description": JOB_AD})).json()

    assert [(d["entry"], d["source_id"]) for d in result["dropped"]] == [
        ("Software engineer, Kente Labs", "b-kl-1")
    ]
    first = result["changes"][0]
    assert (first["entry"], first["rationale"]) == (
        "Lead data engineer, Northwind Consulting",
        "Leads with team size.",
    )
    client_change = next(c for c in result["changes"] if c["source_id"] == "b-hb-1")
    assert (
        client_change["entry"] == "Lead data engineer, Northwind Consulting (Client: Harbour Bank)"
    )


async def test_uses_the_default_template_and_validates_input(
    client: AsyncClient, sample_content: dict[str, Any]
) -> None:
    profile_id = await make_profile(client, sample_content)
    await client.patch("/api/v1/me", json={"default_template_id": "compact"})

    made = await tailor(client, profile_id=profile_id, job={"description": JOB_AD})
    both = await tailor(
        client, profile_id=profile_id, job={"description": JOB_AD}, job_id=made.json()["job"]["id"]
    )
    neither = await tailor(client, profile_id=profile_id)

    assert made.json()["document"]["template_id"] == "compact"
    assert (both.status_code, neither.status_code) == (422, 422)


async def test_other_users_profiles_and_jobs_are_not_found(
    client: AsyncClient, other_client: AsyncClient, sample_content: dict[str, Any]
) -> None:
    profile_id = await make_profile(client, sample_content)
    job = (await client.post("/api/v1/jobs", json={"description": JOB_AD})).json()
    own_profile = await make_profile(other_client, sample_content)

    stolen_profile = await tailor(other_client, profile_id=profile_id, job={"description": "x"})
    stolen_job = await tailor(other_client, profile_id=own_profile, job_id=job["id"])

    assert (stolen_profile.status_code, stolen_job.status_code) == (404, 404)
