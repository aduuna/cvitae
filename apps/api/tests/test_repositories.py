"""Repositories against Postgres: user scoping, cascades and the list-page indexes."""

import uuid

import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import Document, DocumentVersion, Profile, User
from api.repositories.documents import DocumentRepository, DocumentVersionRepository
from api.repositories.profiles import ProfileRepository
from api.repositories.users import UserRepository

CONTENT = {"schema_version": 1, "basics": {"name": "A"}, "summary": "", "sections": []}


async def user(session: AsyncSession, email: str) -> User:
    return await UserRepository(session).get_or_create(f"dev:{email}", email)


async def seed(session: AsyncSession, owner: User) -> tuple[Profile, Document, DocumentVersion]:
    profile = await ProfileRepository(session, owner.id).create(
        name="P", is_default=True, content=CONTENT
    )
    doc = await DocumentRepository(session, owner.id).create(
        profile_id=profile.id, name="D", template_id="classic", content=CONTENT
    )
    version = await DocumentVersionRepository(session, owner.id).create(
        document_id=doc.id, reason="manual", content=CONTENT
    )
    return profile, doc, version


async def test_user_a_cannot_read_or_change_user_b_rows(db_session: AsyncSession) -> None:
    ada, bob = await user(db_session, "ada@example.com"), await user(db_session, "bob@example.com")
    profile, doc, version = await seed(db_session, ada)
    profiles = ProfileRepository(db_session, bob.id)
    documents = DocumentRepository(db_session, bob.id)
    versions = DocumentVersionRepository(db_session, bob.id)

    assert await profiles.get(profile.id) is None
    assert await profiles.list_recent() == []
    assert await profiles.count() == 0
    assert await profiles.delete(profile.id) is False
    await profiles.clear_default()
    assert await documents.get(doc.id) is None
    assert await documents.list_recent() == []
    assert await documents.delete(doc.id) is False
    assert await versions.get(version.id) is None
    assert await versions.list_for(doc.id) == []
    assert await versions.get_number(doc.id, 1) is None
    assert await versions.latest(doc.id) is None
    assert await versions.delete(version.id) is False
    with pytest.raises(LookupError):
        await versions.create(document_id=doc.id, reason="manual", content=CONTENT)

    await db_session.refresh(profile)
    assert profile.is_default is True
    owner = ProfileRepository(db_session, ada.id)
    assert [p.id for p in await owner.list_recent()] == [profile.id]
    assert (await DocumentVersionRepository(db_session, ada.id).latest(doc.id)) == version


async def test_version_numbers_count_up_per_document(db_session: AsyncSession) -> None:
    ada = await user(db_session, "ada@example.com")
    _, doc, first = await seed(db_session, ada)
    versions = DocumentVersionRepository(db_session, ada.id)

    second = await versions.create(document_id=doc.id, reason="autosave", content=CONTENT)

    assert (first.number, second.number) == (1, 2)
    assert [v.number for v in await versions.list_for(doc.id)] == [2, 1]
    assert await versions.get_number(doc.id, 2) == second


async def test_deleting_a_user_cascades(db_session: AsyncSession) -> None:
    ada = await user(db_session, "ada@example.com")
    await seed(db_session, ada)

    await db_session.execute(delete(User).where(User.id == ada.id))

    for model in (Profile, Document, DocumentVersion):
        assert (await db_session.scalars(select(model))).all() == []


async def test_deleting_a_document_deletes_its_versions(db_session: AsyncSession) -> None:
    ada = await user(db_session, "ada@example.com")
    _, doc, _ = await seed(db_session, ada)

    assert await DocumentRepository(db_session, ada.id).delete(doc.id) is True

    assert (await db_session.scalars(select(DocumentVersion))).all() == []


async def test_one_default_profile_per_user(db_session: AsyncSession) -> None:
    ada = await user(db_session, "ada@example.com")
    profiles = ProfileRepository(db_session, ada.id)
    await profiles.create(name="One", is_default=True, content=CONTENT)

    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await profiles.create(name="Two", is_default=True, content=CONTENT)


async def test_get_or_create_user_is_idempotent_and_tracks_email(db_session: AsyncSession) -> None:
    users = UserRepository(db_session)

    first = await users.get_or_create("uid-1", "old@example.com")
    again = await users.get_or_create("uid-1", "new@example.com")

    assert again.id == first.id
    assert again.email == "new@example.com"
    assert (first.plan, first.preferred_ai_model) == ("free", None)


@pytest.mark.parametrize(
    ("table", "index"),
    [
        ("documents", "ix_documents_user_id_updated_at"),
        ("profiles", "ix_profiles_user_id_updated_at"),
    ],
)
async def test_list_pages_use_the_user_updated_index(
    db_session: AsyncSession, table: str, index: str
) -> None:
    await db_session.execute(text("SET LOCAL enable_seqscan = off"))
    plan = await db_session.scalars(
        text(
            f"EXPLAIN SELECT * FROM {table} WHERE user_id = :uid "  # noqa: S608 - fixed names
            "ORDER BY updated_at DESC"
        ),
        {"uid": uuid.uuid4()},
    )

    assert index in "\n".join(plan.all())
