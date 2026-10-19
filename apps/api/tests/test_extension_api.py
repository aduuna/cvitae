"""The browser extension: connecting from the web app, and the routes the extension calls with
its own token."""

import copy
import hashlib
import uuid
from collections.abc import AsyncIterator, Callable
from datetime import timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.base import utcnow
from api.db.models import Document, ExtensionToken, User
from api.services.extension import MAX_CONNECTIONS

JOB = {
    "description": "We are hiring a data engineer to build pipelines on Spark and Kafka.",
    "title": "Data engineer",
    "company": "Harbour Bank",
    "url": "https://boards.example.com/harbour/jobs/42",
}


async def connect(client: AsyncClient, label: str = "Chrome on macOS") -> dict[str, Any]:
    response = await client.post("/api/v1/extension/connections", json={"label": label})
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def make_extension(make_client: Callable[..., AsyncClient]) -> Callable[[str], AsyncClient]:
    """A client that calls as the extension: the token, and no web sign-in."""

    def make(token: str) -> AsyncClient:
        client = make_client(None)
        client.headers["Authorization"] = f"Bearer {token}"
        return client

    return make


@pytest.fixture
async def extension(
    client: AsyncClient, make_extension: Callable[[str], AsyncClient]
) -> AsyncIterator[AsyncClient]:
    async with make_extension((await connect(client))["token"]) as c:
        yield c


async def make_profile(client: AsyncClient, content: dict[str, Any]) -> str:
    response = await client.post("/api/v1/profiles", json={"name": "Data", "content": content})
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def make_document(client: AsyncClient, profile_id: str) -> str:
    response = await client.post("/api/v1/documents", json={"profile_id": profile_id})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def without_placeholders(content: dict[str, Any]) -> dict[str, Any]:
    content = copy.deepcopy(content)
    bullet = content["sections"][0]["experience"][0]["engagements"][0]["bullets"][1]
    bullet["text"] = "Built a streaming fraud-signal pipeline on Kafka."
    return content


async def test_connect_shows_the_token_once(client: AsyncClient) -> None:
    created = await connect(client)

    assert created["token"].startswith("cvx_")
    assert len(created["token"]) > 40
    assert created["label"] == "Chrome on macOS"
    assert created["last_used_at"] is None
    listed = (await client.get("/api/v1/extension/connections")).json()
    assert listed == [{k: v for k, v in created.items() if k != "token"}]


async def test_only_the_tokens_hash_is_stored(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    token = (await connect(client))["token"]

    row = (await db_session.scalars(select(ExtensionToken))).one()
    assert row.token_hash == hashlib.sha256(token.encode()).hexdigest()
    assert token not in (row.label, row.token_hash)


async def test_blank_label_gets_a_name(client: AsyncClient) -> None:
    assert (await connect(client, "  "))["label"] == "Browser extension"


async def test_session_lists_what_forms_can_be_filled_from(
    client: AsyncClient, extension: AsyncClient, sample_content: dict[str, Any]
) -> None:
    profile_id = await make_profile(client, sample_content)
    document_id = await make_document(client, profile_id)
    job = (await client.post("/api/v1/jobs", json=JOB)).json()

    response = await extension.get("/api/v1/extension/session")

    assert response.status_code == 200
    session = response.json()
    assert session["email"] == "ada@example.com"
    assert [(p["id"], p["name"], p["is_default"]) for p in session["profiles"]] == [
        (profile_id, "Data", True)
    ]
    assert [(d["id"], d["name"], d["placeholders"]) for d in session["documents"]] == [
        (document_id, "Data CV", 1)
    ]
    assert [(j["id"], j["url"]) for j in session["jobs"]] == [(job["id"], JOB["url"])]


async def test_session_leaves_out_ejected_cvs(
    client: AsyncClient,
    extension: AsyncClient,
    sample_content: dict[str, Any],
    db_session: AsyncSession,
) -> None:
    document_id = await make_document(client, await make_profile(client, sample_content))
    await db_session.execute(
        update(Document).where(Document.id == uuid.UUID(document_id)).values(mode="ejected")
    )

    session = (await extension.get("/api/v1/extension/session")).json()

    assert session["documents"] == []


async def test_extension_routes_need_the_token(
    make_client: Callable[..., AsyncClient], make_extension: Callable[[str], AsyncClient]
) -> None:
    # Signed in to the web app (dev auth) is not enough.
    async with make_client() as web:
        response = await web.get("/api/v1/extension/session")
        assert response.status_code == 401
        assert response.json()["error"]["message"] == "Connect the extension to your account first."

    async with make_extension("cvx_not-a-real-token") as fake:
        response = await fake.get("/api/v1/extension/session")
        assert response.status_code == 401
        assert response.json()["error"]["message"] == (
            "This browser is no longer connected. Connect the extension again."
        )


async def test_the_token_works_on_extension_routes_only(extension: AsyncClient) -> None:
    assert (await extension.get("/api/v1/profiles")).status_code == 401
    assert (await extension.get("/api/v1/extension/connections")).status_code == 401


async def test_disconnecting_from_settings_revokes_the_token(
    client: AsyncClient, make_extension: Callable[[str], AsyncClient]
) -> None:
    created = await connect(client)

    response = await client.delete(f"/api/v1/extension/connections/{created['id']}")

    assert response.status_code == 204
    async with make_extension(created["token"]) as revoked:
        assert (await revoked.get("/api/v1/extension/session")).status_code == 401
    assert (await client.get("/api/v1/extension/connections")).json() == []


async def test_the_extension_can_disconnect_itself(
    client: AsyncClient, extension: AsyncClient
) -> None:
    assert (await extension.delete("/api/v1/extension/session")).status_code == 204

    assert (await extension.get("/api/v1/extension/session")).status_code == 401
    assert (await client.get("/api/v1/extension/connections")).json() == []


async def test_connections_are_private(client: AsyncClient, other_client: AsyncClient) -> None:
    created = await connect(client)

    assert (await other_client.get("/api/v1/extension/connections")).json() == []
    response = await other_client.delete(f"/api/v1/extension/connections/{created['id']}")
    assert response.status_code == 404
    assert len((await client.get("/api/v1/extension/connections")).json()) == 1


async def test_a_token_reads_only_its_users_data(
    client: AsyncClient,
    other_client: AsyncClient,
    make_extension: Callable[[str], AsyncClient],
    sample_content: dict[str, Any],
) -> None:
    profile_id = await make_profile(client, sample_content)
    document_id = await make_document(client, profile_id)
    bob_token = (await connect(other_client))["token"]

    async with make_extension(bob_token) as bob:
        session = (await bob.get("/api/v1/extension/session")).json()
        assert session["email"] == "bob@example.com"
        assert session["profiles"] == []
        for path in (
            f"profiles/{profile_id}/application",
            f"documents/{document_id}/application",
            f"documents/{document_id}/cv.pdf",
        ):
            assert (await bob.get(f"/api/v1/extension/{path}")).status_code == 404, path


async def test_a_deleted_account_is_refused(
    client: AsyncClient, extension: AsyncClient, db_session: AsyncSession
) -> None:
    await db_session.execute(
        update(User).where(User.email == "ada@example.com").values(deleted_at=utcnow())
    )

    assert (await extension.get("/api/v1/extension/session")).status_code == 401


async def test_last_use_is_recorded_at_most_hourly(
    client: AsyncClient, extension: AsyncClient, db_session: AsyncSession
) -> None:
    await extension.get("/api/v1/extension/session")
    first = (await client.get("/api/v1/extension/connections")).json()[0]["last_used_at"]
    assert first is not None

    await extension.get("/api/v1/extension/session")
    assert (await client.get("/api/v1/extension/connections")).json()[0]["last_used_at"] == first

    await db_session.execute(
        update(ExtensionToken).values(last_used_at=utcnow() - timedelta(hours=2))
    )
    await extension.get("/api/v1/extension/session")
    later = (await client.get("/api/v1/extension/connections")).json()[0]["last_used_at"]
    assert later > first


async def test_too_many_connections_drop_the_least_recently_used(
    client: AsyncClient, extension: AsyncClient
) -> None:
    await extension.get("/api/v1/extension/session")  # the first connection is in use
    for n in range(MAX_CONNECTIONS):
        await connect(client, f"Browser {n}")

    labels = [c["label"] for c in (await client.get("/api/v1/extension/connections")).json()]
    assert len(labels) == MAX_CONNECTIONS
    assert "Chrome on macOS" in labels
    assert "Browser 0" not in labels


async def test_profile_application_data(
    client: AsyncClient, extension: AsyncClient, sample_content: dict[str, Any]
) -> None:
    profile_id = await make_profile(client, sample_content)

    response = await extension.get(f"/api/v1/extension/profiles/{profile_id}/application")

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == {
        "full": "Ama Owusu-Mensah",
        "first": "Ama",
        "middle": "",
        "last": "Owusu-Mensah",
    }
    assert data["location"]["country_code"] == "GB"
    assert data["current_company"] == "Northwind Consulting"
    assert len(data["experience"]) == 3
    assert data["placeholders"] == 1


async def test_document_application_data_follows_the_cv(
    client: AsyncClient, extension: AsyncClient, sample_content: dict[str, Any]
) -> None:
    document_id = await make_document(client, await make_profile(client, sample_content))
    edited = copy.deepcopy(sample_content)
    edited["basics"]["headline"] = "Staff data engineer"
    await client.patch(f"/api/v1/documents/{document_id}", json={"content": edited})

    data = (await extension.get(f"/api/v1/extension/documents/{document_id}/application")).json()

    assert data["headline"] == "Staff data engineer"


async def test_pdf_is_refused_while_placeholders_remain(
    client: AsyncClient, extension: AsyncClient, sample_content: dict[str, Any]
) -> None:
    document_id = await make_document(client, await make_profile(client, sample_content))

    response = await extension.get(f"/api/v1/extension/documents/{document_id}/cv.pdf")

    assert response.status_code == 409
    assert response.json()["error"]["details"]["placeholders"][0]["text"] == "number of analysts"


async def test_pdf_is_named_for_the_jobs_company(
    client: AsyncClient,
    extension: AsyncClient,
    sample_content: dict[str, Any],
    db_session: AsyncSession,
) -> None:
    profile_id = await make_profile(client, without_placeholders(sample_content))
    plain = await make_document(client, profile_id)
    tailored = await make_document(client, profile_id)
    job = (await client.post("/api/v1/jobs", json=JOB)).json()
    await db_session.execute(
        update(Document)
        .where(Document.id == uuid.UUID(tailored))
        .values(job_id=uuid.UUID(job["id"]))
    )

    response = await extension.get(f"/api/v1/extension/documents/{tailored}/cv.pdf")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")
    assert (
        'filename="Ama-Owusu-Mensah-CV-Harbour-Bank.pdf"'
        in (response.headers["content-disposition"])
    )
    response = await extension.get(f"/api/v1/extension/documents/{plain}/cv.pdf")
    assert 'filename="Ama-Owusu-Mensah-CV.pdf"' in response.headers["content-disposition"]


async def test_save_job_once_per_ad(client: AsyncClient, extension: AsyncClient) -> None:
    first = await extension.post("/api/v1/extension/jobs", json=JOB)

    assert first.status_code == 201
    saved = first.json()
    assert saved["created"] is True
    assert (saved["job"]["title"], saved["job"]["company"]) == ("Data engineer", "Harbour Bank")

    again = await extension.post("/api/v1/extension/jobs", json={**JOB, "title": "Changed"})
    assert again.status_code == 200
    assert again.json() == {"job": saved["job"], "created": False}

    jobs = (await client.get("/api/v1/jobs")).json()
    assert [j["id"] for j in jobs] == [saved["job"]["id"]]


async def test_save_job_without_a_url(extension: AsyncClient) -> None:
    body = {"description": JOB["description"]}

    first = (await extension.post("/api/v1/extension/jobs", json=body)).json()
    second = (await extension.post("/api/v1/extension/jobs", json=body)).json()

    assert first["created"] is second["created"] is True
    assert first["job"]["id"] != second["job"]["id"]


async def test_save_job_validates_input(extension: AsyncClient) -> None:
    response = await extension.post("/api/v1/extension/jobs", json={"description": ""})

    assert response.status_code == 422
