"""Plan limits: what a user has used, and the checks that run before a CV or profile is created or
an AI model is called (docs/PRODUCT.md, Plans and limits). AI runs count per calendar month (UTC).
The messages here are the ones the UI shows at a limit, so they live in one place."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from api.billing.plans import PLANS, UPGRADE, Plan
from api.db.base import utcnow
from api.errors import QuotaExceeded
from api.repositories.ai_runs import AiRunRepository
from api.repositories.documents import DocumentRepository
from api.repositories.profiles import ProfileRepository

Stock = Literal["documents", "profiles"]
"""Things a user keeps, limited by count."""

_NOUNS: dict[Stock, tuple[str, str]] = {
    "documents": ("CV", "CVs"),
    "profiles": ("profile", "profiles"),
}


@dataclass(frozen=True)
class Meter:
    used: int
    limit: int
    message: str | None
    """Why no more can be made; set once the limit is reached."""


@dataclass(frozen=True)
class Usage:
    plan: Plan
    period_start: datetime
    period_end: datetime
    """When the AI runs reset."""
    ai_runs: Meter
    documents: Meter
    profiles: Meter


def month(now: datetime) -> tuple[datetime, datetime]:
    """The calendar month (UTC) around `now`: its first instant and the next month's."""
    start = now.astimezone(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return start, (start + timedelta(days=32)).replace(day=1)


def _day(moment: datetime) -> str:
    return f"{moment.day} {moment:%B}"


def _count(n: int, nouns: tuple[str, str]) -> str:
    return f"{n:,} {nouns[0] if n == 1 else nouns[1]}"


def _ai_message(plan: Plan, used: int, reset: datetime) -> str:
    """The UI calls AI runs "AI usage" and shows no counts (docs/PRODUCT.md, Plans and limits)."""
    limits = PLANS[plan]
    if used >= limits.ai_runs:
        head = "You have used all of this month's AI usage."
    else:
        head = "This needs more AI usage than you have left this month."
    if plan == UPGRADE:
        return f"{head} It resets on {_day(reset)}."
    times = PLANS[UPGRADE].ai_runs // limits.ai_runs
    return f"{head} Upgrade to {PLANS[UPGRADE].label} for {times} times as much."


def _stock_message(stock: Stock, plan: Plan, used: int) -> str:
    limits, nouns = PLANS[plan], _NOUNS[stock]
    limit: int = getattr(limits, stock)
    if used == limit:
        head = f"You have {_count(used, nouns)}, the most on {limits.label}."
    else:
        head = f"You have {_count(used, nouns)} and {limits.label} includes {limit:,}."
    which = "one" if used == limit else "some"
    if plan == UPGRADE:
        return f"{head} Delete {which} to make room."
    upgrade: int = getattr(PLANS[UPGRADE], stock)
    return f"{head} Delete {which} or upgrade to {PLANS[UPGRADE].label} for {upgrade:,}."


async def ai_runs_used(runs: AiRunRepository, plan: Plan, since: datetime) -> int:
    return await runs.count_since(since, succeeded_only=not PLANS[plan].counts_failed_runs)


async def require_ai_runs(
    runs: AiRunRepository, plan: Plan, needed: int = 1, *, now: datetime | None = None
) -> None:
    """Room for `needed` AI runs this month, checked before any model is called."""
    start, reset = month(now or utcnow())
    used = await ai_runs_used(runs, plan, start)
    limit = PLANS[plan].ai_runs
    if used + needed > limit:
        raise QuotaExceeded(
            _ai_message(plan, used, reset),
            {"resource": "ai_runs", "used": used, "limit": limit, "needed": needed},
        )


async def require_room(
    stock: Stock, plan: Plan, repository: DocumentRepository | ProfileRepository
) -> None:
    """Room for one more CV or profile. Over the limit after a downgrade, existing ones stay."""
    used = await repository.count()
    limit: int = getattr(PLANS[plan], stock)
    if used >= limit:
        raise QuotaExceeded(
            _stock_message(stock, plan, used), {"resource": stock, "used": used, "limit": limit}
        )


async def usage(
    plan: Plan,
    runs: AiRunRepository,
    documents: DocumentRepository,
    profiles: ProfileRepository,
    *,
    now: datetime | None = None,
) -> Usage:
    start, reset = month(now or utcnow())
    limits = PLANS[plan]

    def meter(used: int, limit: int, message: str) -> Meter:
        return Meter(used=used, limit=limit, message=message if used >= limit else None)

    runs_used = await ai_runs_used(runs, plan, start)
    documents_used, profiles_used = await documents.count(), await profiles.count()
    return Usage(
        plan=plan,
        period_start=start,
        period_end=reset,
        ai_runs=meter(runs_used, limits.ai_runs, _ai_message(plan, runs_used, reset)),
        documents=meter(
            documents_used, limits.documents, _stock_message("documents", plan, documents_used)
        ),
        profiles=meter(
            profiles_used, limits.profiles, _stock_message("profiles", plan, profiles_used)
        ),
    )
