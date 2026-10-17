"""Plan limits through the API: CVs, profiles and AI runs, and what a downgrade keeps."""

import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import AiRun, Job, Upload
from api.ports.llm.fake import FakeLLMProvider
from api.repositories.users import UserRepository

FIXTURES = Path(__file__).resolve().parents[3] / "templates" / "fixtures"
JOB_AD = (FIXTURES / "job-data-engineer.txt").read_text()

MakePro = Callable[..., Awaitable[None]]


async def user_id(client: AsyncClient) -> uuid.UUID:
    return uuid.UUID((await client.get("/api/v1/me")).json()["id"])


async def use_runs(db_session: AsyncSession, owner: uuid.UUID, count: int) -> None:
    db_session.add_all(
        AiRun(
            user_id=owner,
            task="tailor",
            provider="mimo",
            model="mimo-v2.6-flash",
            prompt_version="1",
            status="succeeded",
        )
        for _ in range(count)
    )
    # Committed, so a refused request's rollback keeps them.
    await db_session.commit()


async def make_profile(client: AsyncClient, content: dict[str, Any]) -> str:
    response = await client.post("/api/v1/profiles", json={"name": "Data", "content": content})
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def new_cv(client: AsyncClient, profile_id: str) -> Any:
    return await client.post("/api/v1/documents", json={"profile_id": profile_id})


def refused(response: Any, resource: str) -> str:
    """The 402 envelope for a limit; returns its message."""
    assert response.status_code == 402, response.text
    error = response.json()["error"]
    assert (error["code"], error["details"]["resource"]) == ("quota_exceeded", resource)
    return error["message"]


async def test_free_keeps_four_cvs(client: AsyncClient, sample_content: dict[str, Any]) -> None:
    profile_id = await make_profile(client, sample_content)
    made = [await new_cv(client, profile_id) for _ in range(4)]
    assert [r.status_code for r in made] == [201] * 4

    fifth = await new_cv(client, profile_id)
    copy = await client.post(f"/api/v1/documents/{made[0].json()['id']}/duplicate")

    message = "You have 4 CVs, the most on Free. Delete one or upgrade to Pro for 100."
    assert refused(fifth, "documents") == message
    assert refused(copy, "documents") == message
    usage = (await client.get("/api/v1/usage")).json()
    assert usage["documents"] == {"used": 4, "limit": 4, "message": message}
    # Deleting one makes room again.
    await client.delete(f"/api/v1/documents/{made[0].json()['id']}")
    assert (await new_cv(client, profile_id)).status_code == 201


async def test_free_keeps_two_profiles(client: AsyncClient, sample_content: dict[str, Any]) -> None:
    profile_id = await make_profile(client, sample_content)
    assert (await client.post("/api/v1/profiles", json={})).status_code == 201

    third = await client.post("/api/v1/profiles", json={})
    copy = await client.post(f"/api/v1/profiles/{profile_id}/duplicate")

    message = "You have 2 profiles, the most on Free. Delete one or upgrade to Pro for 10."
    assert refused(third, "profiles") == message
    assert refused(copy, "profiles") == message
    assert len((await client.get("/api/v1/profiles")).json()) == 2


async def test_pro_has_room_for_more(
    client: AsyncClient, sample_content: dict[str, Any], make_pro: MakePro
) -> None:
    await make_pro()
    profile_id = await make_profile(client, sample_content)

    assert [(await client.post("/api/v1/profiles", json={})).status_code for _ in range(2)] == [
        201
    ] * 2
    assert [(await new_cv(client, profile_id)).status_code for _ in range(5)] == [201] * 5
    usage = (await client.get("/api/v1/usage")).json()
    assert usage["plan"] == "pro"
    assert (usage["documents"]["limit"], usage["profiles"]["limit"]) == (100, 10)
    assert usage["ai_runs"] == {"used": 0, "limit": 150, "message": None}


async def test_a_downgrade_keeps_existing_cvs_usable(
    client: AsyncClient,
    sample_content: dict[str, Any],
    make_pro: MakePro,
    db_session: AsyncSession,
) -> None:
    await make_pro()
    profile_id = await make_profile(client, sample_content)
    ids = [(await new_cv(client, profile_id)).json()["id"] for _ in range(5)]
    await UserRepository(db_session).set_plan(await user_id(client), "free")
    await db_session.commit()

    listed = (await client.get("/api/v1/documents")).json()
    opened = await client.get(f"/api/v1/documents/{ids[4]}")
    preview = await client.post(f"/api/v1/documents/{ids[4]}/preview")
    pdf = await client.get(f"/api/v1/documents/{ids[4]}/export.pdf", params={"force": True})
    edited = await client.patch(f"/api/v1/documents/{ids[4]}", json={"name": "Still mine"})

    assert len(listed) == 5
    assert [r.status_code for r in (opened, preview, pdf, edited)] == [200, 200, 200, 200]
    assert refused(await new_cv(client, profile_id), "documents") == (
        "You have 5 CVs and Free includes 4. Delete some or upgrade to Pro for 100."
    )


async def test_no_ai_runs_left_means_no_model_call(
    client: AsyncClient,
    sample_content: dict[str, Any],
    mimo: FakeLLMProvider,
    db_session: AsyncSession,
) -> None:
    profile_id = await make_profile(client, sample_content)
    await client.delete(f"/api/v1/profiles/{profile_id}")
    await use_runs(db_session, await user_id(client), 20)

    imported = await client.post("/api/v1/imports", data={"text": "Ada Lovelace, engineer"})
    profile_id = await make_profile(client, sample_content)
    tailored = await client.post(
        "/api/v1/tailor", json={"profile_id": profile_id, "job": {"description": JOB_AD}}
    )

    message = "You have used all of this month's AI usage. Upgrade to Pro for 7 times as much."
    assert refused(imported, "ai_runs") == message
    assert refused(tailored, "ai_runs") == message
    assert mimo.requests == []
    usage = (await client.get("/api/v1/usage")).json()
    assert usage["ai_runs"] == {"used": 20, "limit": 20, "message": message}


async def test_a_new_job_takes_two_runs_and_a_saved_analysis_one(
    client: AsyncClient,
    sample_content: dict[str, Any],
    mimo: FakeLLMProvider,
    db_session: AsyncSession,
) -> None:
    profile_id = await make_profile(client, sample_content)
    owner = await user_id(client)
    await use_runs(db_session, owner, 17)
    first = await client.post(
        "/api/v1/tailor", json={"profile_id": profile_id, "job": {"description": JOB_AD}}
    )
    assert first.status_code == 201
    job_id = first.json()["job"]["id"]
    await client.delete(f"/api/v1/documents/{first.json()['document']['id']}")
    mimo.requests.clear()

    # 19 of 20 used: a new job needs 2 runs and is refused before anything is saved.
    new_job = await client.post(
        "/api/v1/tailor", json={"profile_id": profile_id, "job": {"description": JOB_AD}}
    )
    assert refused(new_job, "ai_runs") == (
        "This needs more AI usage than you have left this month. "
        "Upgrade to Pro for 7 times as much."
    )
    assert await db_session.scalar(select(func.count()).select_from(Job)) == 1
    assert mimo.requests == []

    # The saved job is already analysed, so tailoring it again takes the last run.
    again = await client.post("/api/v1/tailor", json={"profile_id": profile_id, "job_id": job_id})
    assert again.status_code == 201
    assert [r.task for r in mimo.requests] == ["tailor"]


async def test_tailoring_needs_room_for_the_cv(
    client: AsyncClient,
    sample_content: dict[str, Any],
    mimo: FakeLLMProvider,
) -> None:
    profile_id = await make_profile(client, sample_content)
    for _ in range(4):
        await new_cv(client, profile_id)

    response = await client.post(
        "/api/v1/tailor", json={"profile_id": profile_id, "job": {"description": JOB_AD}}
    )

    refused(response, "documents")
    assert mimo.requests == []


async def test_import_needs_room_for_the_profile(
    client: AsyncClient,
    sample_content: dict[str, Any],
    mimo: FakeLLMProvider,
    db_session: AsyncSession,
) -> None:
    for _ in range(2):
        await make_profile(client, sample_content)

    response = await client.post(
        "/api/v1/imports", files={"file": ("cv.pdf", (FIXTURES / "sample-cv.pdf").read_bytes())}
    )

    refused(response, "profiles")
    assert mimo.requests == []
    # The file is not kept either.
    assert await db_session.scalar(select(func.count()).select_from(Upload)) == 0


async def test_pro_models_need_pro(
    client: AsyncClient,
    sample_content: dict[str, Any],
    make_pro: MakePro,
) -> None:
    profile_id = await make_profile(client, sample_content)
    body = {"profile_id": profile_id, "job": {"description": JOB_AD}, "ai_model": "claude-sonnet"}

    free = await client.post("/api/v1/tailor", json=body)
    await make_pro()
    pro = await client.post("/api/v1/tailor", json=body)

    assert free.status_code == 402
    assert free.json()["error"]["code"] == "plan_required"
    assert (pro.status_code, pro.json()["ai_model"]) == (201, "claude-sonnet")
