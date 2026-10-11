"""Plan limits: the monthly period, which AI runs count, and the messages shown at a limit."""

import uuid
from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import AiRun
from api.errors import QuotaExceeded
from api.repositories.ai_runs import AiRunRepository
from api.repositories.documents import DocumentRepository
from api.repositories.profiles import ProfileRepository
from api.repositories.users import UserRepository
from api.services import quotas

NOW = datetime(2026, 10, 20, 12, tzinfo=UTC)


async def make_user(db_session: AsyncSession, email: str = "ada@example.com") -> uuid.UUID:
    return (await UserRepository(db_session).get_or_create(f"dev:{email}", email)).id


async def add_runs(
    db_session: AsyncSession, user_id: uuid.UUID, count: int, status: str, at: datetime = NOW
) -> None:
    db_session.add_all(
        AiRun(
            user_id=user_id,
            task="import",
            provider="mimo",
            model="mimo-v2.6-flash",
            prompt_version="1",
            status=status,
            created_at=at,
        )
        for _ in range(count)
    )
    await db_session.flush()


async def add_documents(db_session: AsyncSession, user_id: uuid.UUID, count: int) -> None:
    documents = DocumentRepository(db_session, user_id)
    for n in range(count):
        await documents.create(name=f"CV {n}", template_id="classic", content={})


def test_the_period_is_the_calendar_month_in_utc() -> None:
    assert quotas.month(datetime(2026, 12, 31, 23, 30, tzinfo=UTC)) == (
        datetime(2026, 12, 1, tzinfo=UTC),
        datetime(2027, 1, 1, tzinfo=UTC),
    )
    # Just after midnight on 1 November in UTC+1 is still October in UTC.
    early = datetime(2026, 11, 1, 0, 30, tzinfo=timezone(timedelta(hours=1)))
    assert quotas.month(early)[0] == datetime(2026, 10, 1, tzinfo=UTC)


async def test_free_counts_every_attempt_and_pro_only_successes(db_session: AsyncSession) -> None:
    user_id = await make_user(db_session)
    await add_runs(db_session, user_id, 2, "succeeded")
    await add_runs(db_session, user_id, 1, "failed")
    # Last month's runs never count.
    await add_runs(db_session, user_id, 3, "succeeded", at=datetime(2026, 9, 30, 23, tzinfo=UTC))
    runs = AiRunRepository(db_session, user_id)
    start = quotas.month(NOW)[0]

    assert await quotas.ai_runs_used(runs, "free", start) == 3
    assert await quotas.ai_runs_used(runs, "pro", start) == 2


async def test_ai_runs_stop_at_the_limit_with_the_plan_message(db_session: AsyncSession) -> None:
    user_id = await make_user(db_session)
    runs = AiRunRepository(db_session, user_id)
    await add_runs(db_session, user_id, 4, "succeeded")

    await quotas.require_ai_runs(runs, "free", now=NOW)
    with pytest.raises(QuotaExceeded) as two:
        await quotas.require_ai_runs(runs, "free", 2, now=NOW)
    assert two.value.message == (
        "This needs 2 AI runs and you have 1 left this month. Upgrade to Pro for 150."
    )
    assert two.value.details == {"resource": "ai_runs", "used": 4, "limit": 5, "needed": 2}

    await add_runs(db_session, user_id, 1, "failed")
    with pytest.raises(QuotaExceeded) as spent:
        await quotas.require_ai_runs(runs, "free", now=NOW)
    assert spent.value.message == (
        "You have used all 5 AI runs this month. Upgrade to Pro for 150."
    )


async def test_pro_runs_reset_next_month(db_session: AsyncSession) -> None:
    user_id = await make_user(db_session)
    runs = AiRunRepository(db_session, user_id)
    await add_runs(db_session, user_id, 150, "succeeded")
    await add_runs(db_session, user_id, 10, "failed")

    with pytest.raises(QuotaExceeded) as error:
        await quotas.require_ai_runs(runs, "pro", now=NOW)

    assert error.value.message == (
        "You have used all 150 AI runs this month. They reset on 1 November."
    )
    await quotas.require_ai_runs(runs, "pro", now=datetime(2026, 11, 1, tzinfo=UTC))


@pytest.mark.parametrize(
    ("count", "message"),
    [
        (3, "You have 3 CVs, the most on Free. Delete one or upgrade to Pro for 100."),
        # After a downgrade, the CVs above the limit stay.
        (5, "You have 5 CVs and Free includes 3. Delete some or upgrade to Pro for 100."),
    ],
)
async def test_cvs_stop_at_the_limit(db_session: AsyncSession, count: int, message: str) -> None:
    user_id = await make_user(db_session)
    await add_documents(db_session, user_id, count)
    documents = DocumentRepository(db_session, user_id)

    with pytest.raises(QuotaExceeded) as error:
        await quotas.require_room("documents", "free", documents)

    assert error.value.message == message
    assert error.value.details == {"resource": "documents", "used": count, "limit": 3}
    await quotas.require_room("documents", "pro", documents)


async def test_one_profile_on_free(db_session: AsyncSession) -> None:
    user_id = await make_user(db_session)
    profiles = ProfileRepository(db_session, user_id)
    await quotas.require_room("profiles", "free", profiles)
    await profiles.create(name="Data", is_default=True, content={})

    with pytest.raises(QuotaExceeded) as error:
        await quotas.require_room("profiles", "free", profiles)

    assert error.value.message == (
        "You have 1 profile, the most on Free. Delete one or upgrade to Pro for 10."
    )


async def test_usage_has_a_meter_for_each_limit(db_session: AsyncSession) -> None:
    user_id = await make_user(db_session)
    other = await make_user(db_session, "bob@example.com")
    await add_runs(db_session, user_id, 5, "succeeded")
    await add_runs(db_session, other, 2, "succeeded")
    await add_documents(db_session, user_id, 2)

    usage = await quotas.usage(
        "free",
        AiRunRepository(db_session, user_id),
        DocumentRepository(db_session, user_id),
        ProfileRepository(db_session, user_id),
        now=NOW,
    )

    assert (usage.plan, usage.period_start, usage.period_end) == (
        "free",
        datetime(2026, 10, 1, tzinfo=UTC),
        datetime(2026, 11, 1, tzinfo=UTC),
    )
    assert usage.ai_runs == quotas.Meter(
        used=5,
        limit=5,
        message="You have used all 5 AI runs this month. Upgrade to Pro for 150.",
    )
    assert usage.documents == quotas.Meter(used=2, limit=3, message=None)
    assert usage.profiles == quotas.Meter(used=0, limit=1, message=None)
