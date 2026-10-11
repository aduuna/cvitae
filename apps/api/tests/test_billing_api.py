"""Usage, checkout, verification after Paystack's redirect, and the management link."""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_billing
from api.ports.billing import FakePaystackClient
from api.repositories.subscriptions import SubscriptionRepository
from api.repositories.users import UserRepository

PLAN = "PLN_pro_test"


async def user_id(client: AsyncClient) -> uuid.UUID:
    return uuid.UUID((await client.get("/api/v1/me")).json()["id"])


async def test_usage_of_a_new_user(client: AsyncClient) -> None:
    response = await client.get("/api/v1/usage")

    assert response.status_code == 200
    usage = response.json()
    assert usage["plan"] == "free"
    assert usage["ai_runs"] == {"used": 0, "limit": 5, "message": None}
    assert usage["documents"] == {"used": 0, "limit": 3, "message": None}
    assert usage["profiles"] == {"used": 0, "limit": 1, "message": None}
    assert usage["subscription"] is None
    start = datetime.fromisoformat(usage["period_start"])
    end = datetime.fromisoformat(usage["period_end"])
    assert (start.day, start.hour, end.day) == (1, 0, 1)
    assert start <= datetime.now(UTC) < end


async def test_usage_needs_sign_in(make_client: Callable[..., AsyncClient]) -> None:
    async with make_client(None) as anonymous:
        response = await anonymous.get("/api/v1/usage")
    assert response.status_code == 401


async def test_upgrade_through_checkout_and_verify(
    client: AsyncClient, paystack: FakePaystackClient
) -> None:
    owner = await user_id(client)

    started = await client.post("/api/v1/billing/checkout")

    assert started.status_code == 200
    assert started.json() == {"authorization_url": "https://checkout.paystack.test/ref_1"}
    assert paystack.checkouts == [
        {
            "email": "ada@example.com",
            "plan_code": PLAN,
            "callback_url": "http://test/app/settings?tab=billing",
            "metadata": {"user_id": str(owner)},
            "reference": "ref_1",
        }
    ]

    # Back from Paystack before paying: nothing changes.
    unpaid = await client.post("/api/v1/billing/verify", json={"reference": "ref_1"})
    assert unpaid.status_code == 422
    assert (await client.get("/api/v1/me")).json()["plan"] == "free"

    paystack.pay("ref_1")
    for _ in range(2):  # Verifying again is harmless.
        verified = await client.post("/api/v1/billing/verify", json={"reference": "ref_1"})
        assert (verified.status_code, verified.json()) == (200, {"plan": "pro"})

    assert (await client.get("/api/v1/me")).json()["plan"] == "pro"
    usage = (await client.get("/api/v1/usage")).json()
    assert (usage["plan"], usage["ai_runs"]["limit"], usage["documents"]["limit"]) == (
        "pro",
        150,
        100,
    )
    # Paystack's subscription code arrives with the webhook; until then there is nothing to manage.
    assert usage["subscription"] == {
        "status": "active",
        "current_period_end": None,
        "manageable": False,
    }
    again = await client.post("/api/v1/billing/checkout")
    assert (again.status_code, again.json()["error"]["code"]) == (409, "conflict")


async def test_an_old_payment_does_not_bring_pro_back(
    client: AsyncClient, paystack: FakePaystackClient, db_session: AsyncSession
) -> None:
    await client.post("/api/v1/billing/checkout")
    paystack.pay("ref_1")
    await client.post("/api/v1/billing/verify", json={"reference": "ref_1"})
    # The subscription ends; the user tries the same reference again.
    await UserRepository(db_session).set_plan(await user_id(client), "free")
    await db_session.commit()

    again = await client.post("/api/v1/billing/verify", json={"reference": "ref_1"})

    assert (again.status_code, again.json()) == (200, {"plan": "free"})
    assert (await client.get("/api/v1/me")).json()["plan"] == "free"


async def test_no_second_subscription_while_a_payment_needs_a_new_card(
    client: AsyncClient, paystack: FakePaystackClient, db_session: AsyncSession
) -> None:
    await SubscriptionRepository(db_session, await user_id(client)).save(
        paystack_customer_code="CUS_ada",
        paystack_subscription_code="SUB_ada_1",
        plan_code=PLAN,
        status="attention",
        current_period_end=datetime(2026, 1, 1, tzinfo=UTC),
    )
    await db_session.commit()

    response = await client.post("/api/v1/billing/checkout")

    assert response.status_code == 409
    assert "Update your card" in response.json()["error"]["message"]
    assert paystack.checkouts == []


async def test_someone_elses_payment_is_not_found(
    client: AsyncClient, other_client: AsyncClient, paystack: FakePaystackClient
) -> None:
    await client.post("/api/v1/billing/checkout")
    paystack.pay("ref_1")

    stolen = await other_client.post("/api/v1/billing/verify", json={"reference": "ref_1"})
    unknown = await client.post("/api/v1/billing/verify", json={"reference": "ref_404"})
    malformed = await client.post("/api/v1/billing/verify", json={"reference": "../x"})

    assert (stolen.status_code, unknown.status_code, malformed.status_code) == (404, 404, 422)
    assert (await other_client.get("/api/v1/me")).json()["plan"] == "free"


async def test_a_payment_for_another_plan_does_not_upgrade(
    client: AsyncClient, paystack: FakePaystackClient
) -> None:
    await client.post("/api/v1/billing/checkout")
    paystack.pay("ref_1")
    paid = paystack.transactions["ref_1"]
    paystack.transactions["ref_1"] = paid.model_copy(update={"plan_code": "PLN_other"})

    response = await client.post("/api/v1/billing/verify", json={"reference": "ref_1"})

    assert response.status_code == 422
    assert (await client.get("/api/v1/me")).json()["plan"] == "free"


async def test_manage_link(
    client: AsyncClient, paystack: FakePaystackClient, db_session: AsyncSession
) -> None:
    missing = await client.get("/api/v1/billing/manage-link")
    assert missing.status_code == 404

    await SubscriptionRepository(db_session, await user_id(client)).save(
        paystack_customer_code="CUS_ada",
        paystack_subscription_code="SUB_ada_1",
        plan_code=PLAN,
        status="active",
    )
    response = await client.get("/api/v1/billing/manage-link")

    assert response.json() == {"url": "https://paystack.test/manage/subscriptions/SUB_ada_1"}
    assert paystack.manage_links == ["SUB_ada_1"]


async def test_billing_routes_need_billing_set_up(app: FastAPI, client: AsyncClient) -> None:
    del app.dependency_overrides[get_billing]

    checkout = await client.post("/api/v1/billing/checkout")
    verify = await client.post("/api/v1/billing/verify", json={"reference": "ref_1"})
    link = await client.get("/api/v1/billing/manage-link")

    assert [r.status_code for r in (checkout, verify, link)] == [503, 503, 503]
    assert checkout.json()["error"]["message"] == "Upgrades are not available on this server yet."
