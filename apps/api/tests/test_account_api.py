"""Account export and deletion: everything is exported, nothing is left behind, and one user's
account never touches another's."""

import json
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import Table, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.base import Base
from api.db.models import Document, DocumentVersion, ExtensionToken, User
from api.deps import get_storage
from api.errors import NotFound
from api.ports.storage import LocalStorage
from api.repositories.ai_runs import AiRunRepository
from api.repositories.subscriptions import SubscriptionRepository
from api.repositories.uploads import UploadRepository
from api.repositories.user_templates import UserTemplateRepository
from api.services import uploads as upload_service

PDF = b"%PDF-1.7\n1 0 obj\n"
ME = "/api/v1/me"


async def user_id(client: AsyncClient) -> uuid.UUID:
    return uuid.UUID((await client.get(ME)).json()["id"])


async def seed(client: AsyncClient, db_session: AsyncSession, storage: LocalStorage) -> None:
    """Something in every place an account keeps data, made as the account's owner would."""
    owner = await user_id(client)
    profile = (await client.post("/api/v1/profiles", json={"name": "Data"})).json()
    document = (await client.post("/api/v1/documents", json={"profile_id": profile["id"]})).json()
    await client.post(f"/api/v1/documents/{document['id']}/versions")
    await client.post(
        "/api/v1/jobs", json={"description": "Spark and Kafka", "title": "Engineer", "company": "X"}
    )
    await client.post("/api/v1/extension/connections", json={"label": "Chrome on macOS"})
    await upload_service.store_upload(UploadRepository(db_session, owner), storage, "cv.pdf", PDF)
    await AiRunRepository(db_session, owner).create(
        task="import",
        provider="mimo",
        model="mimo-v2.6-flash",
        prompt_version="1",
        status="succeeded",
        input_tokens=120,
        output_tokens=80,
    )
    await UserTemplateRepository(db_session, owner).create(
        slug=f"u-{owner.hex[:10]}",
        name="Mine",
        description="From my CV",
        main_typ="#set page()",
        paper_sizes=["a4"],
        target_pages=1,
        status="ready",
        prompt_version="1",
    )
    await SubscriptionRepository(db_session, owner).save(
        paystack_customer_code="CUS_1",
        paystack_subscription_code="SUB_1",
        plan_code="PLN_pro",
        status="cancelled",
        current_period_end=datetime(2026, 1, 1, tzinfo=UTC),
    )
    await db_session.commit()


def user_owned_tables() -> list[Table]:
    """The tables with a `user_id` column."""
    return [t for t in Base.metadata.sorted_tables if "user_id" in t.c]


async def rows_left(
    session: AsyncSession, owner: uuid.UUID, documents: list[uuid.UUID]
) -> dict[str, int]:
    """How many rows of the account remain in each table, by table name."""
    counts: dict[str, int] = {}
    for table in user_owned_tables():
        stmt = select(func.count()).select_from(table).where(table.c.user_id == owner)
        counts[table.name] = await session.scalar(stmt) or 0
    versions = select(func.count()).select_from(DocumentVersion)
    counts["document_versions"] = (
        await session.scalar(versions.where(DocumentVersion.document_id.in_(documents))) or 0
    )
    users = select(func.count()).select_from(User).where(User.id == owner)
    counts["users"] = await session.scalar(users) or 0
    return counts


async def document_ids(session: AsyncSession, owner: uuid.UUID) -> list[uuid.UUID]:
    rows = await session.scalars(select(Document.id).where(Document.user_id == owner))
    return list(rows)


def files_under(root: Path, owner: uuid.UUID) -> list[Path]:
    folder = root / "uploads" / str(owner)
    return [p for p in folder.rglob("*") if p.is_file()] if folder.is_dir() else []


# Export


async def test_export_holds_everything_the_account_has(
    client: AsyncClient, db_session: AsyncSession, storage: LocalStorage
) -> None:
    await client.patch(ME, json={"display_name": "Ada"})
    await seed(client, db_session, storage)
    owner = await user_id(client)

    response = await client.get(f"{ME}/export")

    assert response.status_code == 200
    assert response.headers["content-disposition"] == (
        'attachment; filename="chameleon-vitae-export.json"'
    )
    export = response.json()
    assert export["account"]["email"] == "ada@example.com"
    assert export["account"]["display_name"] == "Ada"
    assert [p["name"] for p in export["profiles"]] == ["Data"]
    assert export["profiles"][0]["content"]["schema_version"] == 1
    assert [j["description"] for j in export["jobs"]] == ["Spark and Kafka"]
    [document] = export["documents"]
    assert document["name"] == "Data CV"
    assert document["content"]["sections"]
    assert [(v["number"], v["reason"]) for v in document["versions"]] == [(1, "manual")]
    assert [(t["id"], t["main_typ"]) for t in export["templates"]] == [
        (f"u-{owner.hex[:10]}", "#set page()")
    ]
    assert [(u["filename"], u["size_bytes"]) for u in export["uploads"]] == [("cv.pdf", len(PDF))]
    assert [(r["task"], r["input_tokens"]) for r in export["ai_runs"]] == [("import", 120)]
    assert export["subscription"]["status"] == "cancelled"
    assert [c["label"] for c in export["extension_connections"]] == ["Chrome on macOS"]
    assert export["exported_at"]


async def test_export_of_a_new_account_is_empty(client: AsyncClient) -> None:
    export = (await client.get(f"{ME}/export")).json()

    assert export["account"]["email"] == "ada@example.com"
    for part in ("profiles", "jobs", "documents", "templates", "uploads", "ai_runs"):
        assert export[part] == []
    assert export["subscription"] is None
    assert export["extension_connections"] == []


async def test_export_is_only_the_signed_in_users_data(
    client: AsyncClient,
    other_client: AsyncClient,
    db_session: AsyncSession,
    storage: LocalStorage,
) -> None:
    await seed(other_client, db_session, storage)
    bob = await user_id(other_client)

    export = (await client.get(f"{ME}/export")).json()

    assert export["profiles"] == export["documents"] == export["jobs"] == []
    assert export["uploads"] == export["templates"] == export["ai_runs"] == []
    assert str(bob) not in json.dumps(export)
    assert "bob@example.com" not in json.dumps(export)


async def test_export_has_no_extension_token_or_hash(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    token = (await client.post("/api/v1/extension/connections", json={"label": "Chrome"})).json()[
        "token"
    ]

    text = (await client.get(f"{ME}/export")).text

    stored = (await db_session.scalars(select(ExtensionToken.token_hash))).all()
    assert token not in text
    assert stored
    assert all(digest not in text for digest in stored)


async def test_export_needs_sign_in(make_client: Callable[..., AsyncClient]) -> None:
    async with make_client(user=None) as anonymous:
        response = await anonymous.get(f"{ME}/export")

    assert response.status_code == 401


# Deletion


def test_every_table_is_removed_with_its_user() -> None:
    """A table added later that does not cascade from `users` fails here, before it can leave
    rows behind. Only webhook events are not user data."""
    tables = Base.metadata.tables

    def cascades_from_users(table: Table, seen: frozenset[str] = frozenset()) -> bool:
        for fk in table.foreign_keys:
            parent = fk.column.table
            if fk.ondelete != "CASCADE" or parent.name in seen:
                continue
            if parent.name == "users" or cascades_from_users(parent, seen | {table.name}):
                return True
        return False

    owned = {name for name, table in tables.items() if name not in ("users", "webhook_events")}
    assert owned == {
        "profiles",
        "jobs",
        "documents",
        "document_versions",
        "uploads",
        "ai_runs",
        "user_templates",
        "subscriptions",
        "extension_tokens",
    }
    assert [name for name in sorted(owned) if not cascades_from_users(tables[name])] == []
    assert "user_id" not in tables["webhook_events"].c


async def test_deleting_the_account_leaves_no_rows_and_no_files(
    client: AsyncClient, db_session: AsyncSession, storage: LocalStorage, tmp_path: Path
) -> None:
    await seed(client, db_session, storage)
    owner = await user_id(client)
    documents = await document_ids(db_session, owner)
    before = await rows_left(db_session, owner, documents)
    assert files_under(tmp_path / "storage", owner)
    assert all(count > 0 for count in before.values()), before

    response = await client.request("DELETE", ME, json={"email": "ada@example.com"})

    assert response.status_code == 204
    after = await rows_left(db_session, owner, documents)
    assert {name: count for name, count in after.items() if count} == {}
    assert set(after) == set(before)
    assert files_under(tmp_path / "storage", owner) == []
    with pytest.raises(NotFound):
        await storage.get(f"uploads/{owner}/{uuid.uuid4()}")


async def test_the_email_is_matched_without_regard_to_case_or_spaces(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    owner = await user_id(client)

    response = await client.request("DELETE", ME, json={"email": "  ADA@Example.com "})

    assert response.status_code == 204
    assert await db_session.get(User, owner) is None


async def test_a_wrong_email_deletes_nothing(
    client: AsyncClient, db_session: AsyncSession, storage: LocalStorage, tmp_path: Path
) -> None:
    await seed(client, db_session, storage)
    owner = await user_id(client)

    for email in ("", "ada@example.org", "bob@example.com"):
        response = await client.request("DELETE", ME, json={"email": email})
        assert response.status_code == 422
        assert response.json()["error"]["details"] == {"field": "email"}

    assert await db_session.get(User, owner) is not None
    assert len((await client.get("/api/v1/profiles")).json()) == 1
    assert len(files_under(tmp_path / "storage", owner)) == 1


async def test_deleting_needs_the_confirmation_in_the_body(client: AsyncClient) -> None:
    response = await client.request("DELETE", ME)

    assert response.status_code == 422


async def test_deleting_needs_sign_in(make_client: Callable[..., AsyncClient]) -> None:
    async with make_client(user=None) as anonymous:
        response = await anonymous.request("DELETE", ME, json={"email": "ada@example.com"})

    assert response.status_code == 401


async def test_one_account_cannot_delete_another(
    client: AsyncClient,
    other_client: AsyncClient,
    db_session: AsyncSession,
    storage: LocalStorage,
    tmp_path: Path,
) -> None:
    await seed(client, db_session, storage)
    await seed(other_client, db_session, storage)
    ada, bob = await user_id(client), await user_id(other_client)
    ada_documents, bob_documents = (
        await document_ids(db_session, ada),
        await document_ids(db_session, bob),
    )
    bobs_before = await rows_left(db_session, bob, bob_documents)

    # Ada cannot delete Bob by typing his address: the confirmation is her own.
    refused = await client.request("DELETE", ME, json={"email": "bob@example.com"})
    assert refused.status_code == 422
    assert await rows_left(db_session, bob, bob_documents) == bobs_before

    # Deleting Ada leaves every row and file of Bob's.
    assert (
        await client.request("DELETE", ME, json={"email": "ada@example.com"})
    ).status_code == 204
    assert {n: c for n, c in (await rows_left(db_session, ada, ada_documents)).items() if c} == {}
    assert await rows_left(db_session, bob, bob_documents) == bobs_before
    assert len(files_under(tmp_path / "storage", bob)) == 1
    assert files_under(tmp_path / "storage", ada) == []
    export = (await other_client.get(f"{ME}/export")).json()
    assert [p["name"] for p in export["profiles"]] == ["Data"]
    assert len(export["documents"][0]["versions"]) == 1


async def test_signing_in_again_starts_an_empty_account(
    client: AsyncClient, db_session: AsyncSession, storage: LocalStorage
) -> None:
    await seed(client, db_session, storage)
    old = await user_id(client)

    await client.request("DELETE", ME, json={"email": "ada@example.com"})

    assert await user_id(client) != old
    assert (await client.get("/api/v1/profiles")).json() == []
    assert (await client.get("/api/v1/uploads")).json() == []


async def test_a_deleted_accounts_extension_token_stops_working(
    client: AsyncClient, make_client: Callable[..., AsyncClient]
) -> None:
    token = (await client.post("/api/v1/extension/connections", json={"label": "Chrome"})).json()[
        "token"
    ]
    async with make_client(user=None) as extension:
        headers = {"Authorization": f"Bearer {token}"}
        assert (
            await extension.get("/api/v1/extension/session", headers=headers)
        ).status_code == 200

        await client.request("DELETE", ME, json={"email": "ada@example.com"})

        assert (
            await extension.get("/api/v1/extension/session", headers=headers)
        ).status_code == 401


@pytest.mark.parametrize(
    ("status", "deleted"),
    [("active", False), ("attention", False), ("non_renewing", True), ("cancelled", True)],
)
async def test_a_subscription_that_is_still_charged_is_cancelled_first(
    client: AsyncClient, db_session: AsyncSession, status: str, deleted: bool
) -> None:
    owner = await user_id(client)
    await SubscriptionRepository(db_session, owner).save(
        paystack_customer_code="CUS_1", plan_code="PLN_pro", status=status
    )
    await db_session.commit()

    response = await client.request("DELETE", ME, json={"email": "ada@example.com"})

    assert (response.status_code == 204) is deleted
    assert (await db_session.get(User, owner) is None) is deleted
    if not deleted:
        assert response.status_code == 409
        assert "Cancel your Pro subscription" in response.json()["error"]["message"]


class FailingStorage(LocalStorage):
    async def delete_prefix(self, prefix: str) -> int:
        raise RuntimeError("storage is down")


async def test_a_storage_failure_leaves_the_account_whole(
    app: FastAPI,
    client: AsyncClient,
    db_session: AsyncSession,
    storage: LocalStorage,
    tmp_path: Path,
) -> None:
    await seed(client, db_session, storage)
    owner = await user_id(client)
    working = app.dependency_overrides[get_storage]
    app.dependency_overrides[get_storage] = lambda: FailingStorage(tmp_path / "storage")

    with pytest.raises(RuntimeError, match="storage is down"):
        await client.request("DELETE", ME, json={"email": "ada@example.com"})

    app.dependency_overrides[get_storage] = working
    assert await db_session.get(User, owner) is not None
    counts = await rows_left(db_session, owner, await document_ids(db_session, owner))
    assert all(count > 0 for count in counts.values()), counts
    # Another try, with storage back, finishes the job.
    response = await client.request("DELETE", ME, json={"email": "ada@example.com"})
    assert response.status_code == 204
    assert files_under(tmp_path / "storage", owner) == []
