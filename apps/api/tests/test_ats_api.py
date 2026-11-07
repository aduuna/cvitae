"""The ATS score of a CV (GET /documents/{id}/ats), linking a job to a CV, and analysing a saved
job (POST /jobs/{id}/analyze)."""

import uuid
from pathlib import Path
from typing import Any

from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import AiRun, Document
from api.ports.llm.fake import FakeLLMProvider

FIXTURES = Path(__file__).resolve().parents[3] / "templates" / "fixtures"

JOB_AD = (FIXTURES / "job-data-engineer.txt").read_text()


async def new_cv(client: AsyncClient, content: dict[str, Any]) -> dict[str, Any]:
    profile = await client.post("/api/v1/profiles", json={"name": "Data", "content": content})
    response = await client.post("/api/v1/documents", json={"profile_id": profile.json()["id"]})
    return response.json()


async def new_job(client: AsyncClient) -> dict[str, Any]:
    return (await client.post("/api/v1/jobs", json={"description": JOB_AD})).json()


async def link(client: AsyncClient, document_id: str, job_id: str) -> Any:
    return await client.patch(f"/api/v1/documents/{document_id}", json={"job_id": job_id})


async def analyze(client: AsyncClient, job_id: str) -> Any:
    return await client.post(f"/api/v1/jobs/{job_id}/analyze", json={})


async def get_ats(client: AsyncClient, document_id: str) -> Any:
    return await client.get(f"/api/v1/documents/{document_id}/ats")


def missing(report: dict[str, Any]) -> list[tuple[str, bool | None]]:
    return [(k["term"], k["in_profile"]) for k in report["keywords"] if not k["found_in"]]


async def test_the_score_needs_a_job_and_its_analysis(
    client: AsyncClient, sample_content: dict[str, Any], mimo: FakeLLMProvider
) -> None:
    doc = await new_cv(client, sample_content)

    assert (await get_ats(client, doc["id"])).json() == {"job": None, "report": None}

    job = await new_job(client)
    linked = await link(client, doc["id"], job["id"])
    assert (linked.status_code, linked.json()["job_id"]) == (200, job["id"])
    unread = (await get_ats(client, doc["id"])).json()
    assert (unread["job"]["id"], unread["report"]) == (job["id"], None)

    analysed = await analyze(client, job["id"])
    assert analysed.status_code == 200
    assert analysed.json()["analysis"]["keywords"][:3] == ["Python", "SQL", "Spark"]
    assert analysed.json()["title"] == "Senior Data Engineer, Payments Platform"
    assert (await analyze(client, job["id"])).status_code == 200
    assert [r.task for r in mimo.requests] == ["analyze_job"]  # analysed once, then kept

    await client.post(f"/api/v1/documents/{doc['id']}/preview")  # records the page count
    response = await get_ats(client, doc["id"])

    assert response.status_code == 200
    report = response.json()["report"]
    # Required Python, SQL and Spark (9 points), preferred Kafka, Airflow, dbt and AWS (8 of 12),
    # the title (3): 20 of 24.
    assert (report["score"], report["band"]) == (83, "strong")
    assert (report["title"], report["title_found"]) == ("Data Engineer", True)
    assert missing(report) == [("Snowflake", False), ("Kubernetes", False)]
    assert [(c["id"], c["ok"]) for c in report["checks"]] == [
        ("contact", True),
        ("headings", True),
        ("placeholders", False),
        ("length", True),
    ]
    assert [r.task for r in mimo.requests] == ["analyze_job"]  # the score itself runs no AI


async def test_keywords_left_out_of_the_cv_are_found_in_the_profile(
    client: AsyncClient, sample_content: dict[str, Any], mimo: FakeLLMProvider
) -> None:
    doc = await new_cv(client, sample_content)
    job = await new_job(client)
    await link(client, doc["id"], job["id"])
    await analyze(client, job["id"])
    content = dict(doc["content"])
    content["sections"] = [s for s in content["sections"] if s["kind"] != "skills"]
    await client.patch(f"/api/v1/documents/{doc['id']}", json={"content": content})

    report = (await get_ats(client, doc["id"])).json()["report"]

    # SQL was only in the skills list, which this CV left out.
    assert missing(report) == [("SQL", True), ("Snowflake", False), ("Kubernetes", False)]

    await client.delete(f"/api/v1/profiles/{doc['profile_id']}")
    report = (await get_ats(client, doc["id"])).json()["report"]

    assert missing(report) == [("SQL", None), ("Snowflake", None), ("Kubernetes", None)]


async def test_deleting_the_job_unlinks_it(
    client: AsyncClient, sample_content: dict[str, Any], mimo: FakeLLMProvider
) -> None:
    doc = await new_cv(client, sample_content)
    job = await new_job(client)
    await link(client, doc["id"], job["id"])

    await client.delete(f"/api/v1/jobs/{job['id']}")

    assert (await get_ats(client, doc["id"])).json() == {"job": None, "report": None}


async def test_an_ejected_cv_has_no_score(
    client: AsyncClient, sample_content: dict[str, Any], db_session: AsyncSession
) -> None:
    doc = await new_cv(client, sample_content)
    await db_session.execute(
        update(Document).where(Document.id == uuid.UUID(doc["id"])).values(mode="ejected")
    )
    await db_session.commit()

    response = await get_ats(client, doc["id"])

    assert response.status_code == 409
    assert response.json()["error"]["message"] == (
        "The ATS score reads the form, and this CV is edited as Typst."
    )
    # Linking a job still works: it names the PDF.
    job = await new_job(client)
    assert (await link(client, doc["id"], job["id"])).status_code == 200


async def test_jobs_and_scores_are_private(
    client: AsyncClient, other_client: AsyncClient, sample_content: dict[str, Any]
) -> None:
    doc = await new_cv(client, sample_content)
    job = await new_job(client)
    theirs = await new_job(other_client)

    for response in [
        await link(client, doc["id"], str(uuid.uuid4())),
        await link(client, doc["id"], theirs["id"]),
        await get_ats(other_client, doc["id"]),
        await analyze(other_client, job["id"]),
        await link(other_client, doc["id"], theirs["id"]),
    ]:
        assert response.status_code == 404, response.request.url
    assert (await client.get(f"/api/v1/documents/{doc['id']}")).json()["job_id"] is None


async def test_analysis_counts_as_ai_usage(
    client: AsyncClient, mimo: FakeLLMProvider, db_session: AsyncSession
) -> None:
    analysed, unread = await new_job(client), await new_job(client)
    await analyze(client, analysed["id"])
    owner = uuid.UUID((await client.get("/api/v1/me")).json()["id"])
    db_session.add_all(
        AiRun(
            user_id=owner,
            task="analyze_job",
            provider="mimo",
            model="mimo-v2.6-flash",
            prompt_version="1",
            status="failed",
        )
        for _ in range(19)
    )
    await db_session.commit()

    refused = await analyze(client, unread["id"])

    assert refused.status_code == 402
    assert refused.json()["error"]["details"]["resource"] == "ai_runs"
    # A job analysed before needs no AI run, so it is not refused.
    assert (await analyze(client, analysed["id"])).status_code == 200
    assert len(mimo.requests) == 1


async def test_the_exported_pdf_is_named_for_the_linked_jobs_company(
    client: AsyncClient, sample_content: dict[str, Any], mimo: FakeLLMProvider
) -> None:
    doc = await new_cv(client, sample_content)
    url = f"/api/v1/documents/{doc['id']}/export.pdf?force=true"
    plain = await client.get(url)
    assert 'filename="Ama-Owusu-Mensah-CV.pdf"' in plain.headers["content-disposition"]

    job = await new_job(client)
    await link(client, doc["id"], job["id"])
    await analyze(client, job["id"])  # reading the ad is what finds the company

    named = await client.get(url)

    assert named.status_code == 200
    assert 'filename="Ama-Owusu-Mensah-CV-Lumen-Payments' in named.headers["content-disposition"]
