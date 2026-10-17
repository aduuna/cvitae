"""POST /webhooks/paystack with signed payloads based on Paystack's documented samples: the
signature check, each event's effect, and replays that change nothing."""

import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from httpx import AsyncClient, Response
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import Subscription, WebhookEvent
from api.deps import get_billing
from api.ports.billing import FakePaystackClient, sign
from api.services.billing import event_key

EVENTS = Path(__file__).parent / "fixtures" / "paystack"


def event(name: str, **data: Any) -> dict[str, Any]:
    """A fixture event with some of its data fields replaced."""
    payload = json.loads((EVENTS / f"{name}.json").read_text())
    payload["data"].update(data)
    return payload


def charge(owner: uuid.UUID | str, **data: Any) -> dict[str, Any]:
    return event("charge_success", metadata={"user_id": str(owner)}, **data)


async def deliver(
    client: AsyncClient, payload: dict[str, Any] | bytes, signature: str | None = None
) -> Response:
    body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    if signature is None:
        signature = sign(FakePaystackClient.SECRET, body)
    return await client.post(
        "/api/v1/webhooks/paystack",
        content=body,
        headers={"x-paystack-signature": signature, "content-type": "application/json"},
    )


async def user_id(client: AsyncClient) -> uuid.UUID:
    return uuid.UUID((await client.get("/api/v1/me")).json()["id"])


async def state(client: AsyncClient) -> tuple[str, dict[str, Any]]:
    """The plan, and the subscription ({} when there is none)."""
    usage = (await client.get("/api/v1/usage")).json()
    return usage["plan"], usage["subscription"] or {}


async def recorded(db_session: AsyncSession) -> int:
    return await db_session.scalar(select(func.count()).select_from(WebhookEvent)) or 0


async def test_unsigned_or_wrongly_signed_events_are_refused(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    owner = await user_id(client)
    body = json.dumps(charge(owner)).encode()

    wrong = await deliver(client, body, signature=sign("sk_test_other", body))
    missing = await client.post("/api/v1/webhooks/paystack", content=body)

    assert (wrong.status_code, missing.status_code) == (401, 401)
    assert wrong.json()["error"]["code"] == "unauthorized"
    assert await recorded(db_session) == 0
    assert (await state(client))[0] == "free"


async def test_the_subscription_lifecycle_and_replays(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    owner = await user_id(client)
    created = event("subscription_create")

    # Paid at checkout: Pro at once; the subscription code follows.
    assert (await deliver(client, charge(owner))).json() == {"status": "ok"}
    assert await state(client) == (
        "pro",
        {"status": "active", "current_period_end": None, "manageable": False},
    )
    await deliver(client, created)
    assert await state(client) == (
        "pro",
        {"status": "active", "current_period_end": "2026-11-10T00:00:00Z", "manageable": True},
    )
    usage = (await client.get("/api/v1/usage")).json()
    assert (usage["ai_runs"]["limit"], usage["documents"]["limit"]) == (150, 100)

    # A renewal is paid: the period moves on.
    await deliver(client, event("invoice_update"))
    assert (await state(client))[1]["current_period_end"] == "2026-12-10T00:00:00Z"

    # Cancelled from Paystack's page: Pro until Paystack disables it.
    await deliver(client, event("subscription_not_renew"))
    plan, subscription = await state(client)
    assert (plan, subscription["status"]) == ("pro", "non_renewing")
    await deliver(client, event("subscription_disable"))
    plan, subscription = await state(client)
    assert (plan, subscription["status"]) == ("free", "cancelled")
    assert (await client.get("/api/v1/usage")).json()["ai_runs"]["limit"] == 20
    assert await recorded(db_session) == 5

    # Paystack delivers the same events again: nothing changes.
    for name in ("charge_success", "subscription_create", "invoice_update"):
        payload = charge(owner) if name == "charge_success" else event(name)
        assert (await deliver(client, payload)).status_code == 200
    plan, subscription = await state(client)
    assert (plan, subscription["status"]) == ("free", "cancelled")
    assert await recorded(db_session) == 5


async def test_a_failed_renewal_keeps_pro_until_the_paid_period_ends(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    owner = await user_id(client)
    paid_until = (datetime.now(UTC) + timedelta(days=3)).isoformat()
    await deliver(client, charge(owner))
    await deliver(client, event("subscription_create", next_payment_date=paid_until))

    await deliver(client, event("invoice_payment_failed"))

    plan, subscription = await state(client)
    assert (plan, subscription["status"]) == ("pro", "attention")
    assert (await client.get("/api/v1/me")).json()["plan"] == "pro"

    # The paid period ends and no payment came through: Free, without any event.
    await db_session.execute(
        update(Subscription).values(current_period_end=datetime.now(UTC) - timedelta(minutes=1))
    )
    await db_session.commit()
    assert (await client.get("/api/v1/me")).json()["plan"] == "free"
    assert (await state(client))[0] == "free"
    pro_model = await client.post("/api/v1/imports", data={"text": "x", "ai_model": "mimo-pro"})
    assert pro_model.json()["error"]["code"] == "plan_required"

    # The card is updated and Paystack retries successfully: Pro again.
    retried = event("invoice_update", invoice_code="INV_ada_dec")
    await deliver(client, retried)
    plan, subscription = await state(client)
    assert (plan, subscription["status"]) == ("pro", "active")


async def test_a_payment_verified_after_the_redirect_is_not_applied_twice(
    client: AsyncClient, paystack: FakePaystackClient, db_session: AsyncSession
) -> None:
    owner = await user_id(client)
    await client.post("/api/v1/billing/checkout")
    paystack.pay("ref_1")
    await client.post("/api/v1/billing/verify", json={"reference": "ref_1"})

    # The webhook for the same charge arrives afterwards: already applied.
    await deliver(client, charge(owner, reference="ref_1"))

    assert (await state(client))[0] == "pro"
    assert await recorded(db_session) == 1


async def test_subscription_create_can_arrive_first(client: AsyncClient) -> None:
    owner = await user_id(client)

    # Not on record yet: found by the email used at checkout.
    await deliver(client, event("subscription_create"))
    assert (await state(client))[0] == "pro"

    await deliver(client, charge(owner))
    assert await state(client) == (
        "pro",
        {"status": "active", "current_period_end": "2026-11-10T00:00:00Z", "manageable": True},
    )


async def test_renewal_charges_find_the_customer_without_our_metadata(
    client: AsyncClient,
) -> None:
    owner = await user_id(client)
    await deliver(client, charge(owner))
    await deliver(client, event("subscription_create"))
    await deliver(client, event("invoice_payment_failed"))

    renewal = event("charge_success", reference="ref_renewal", metadata={"invoice_action": "x"})
    await deliver(client, renewal)

    plan, subscription = await state(client)
    assert (plan, subscription["status"]) == ("pro", "active")


async def test_events_this_app_cannot_use_are_recorded_and_ignored(
    client: AsyncClient, other_client: AsyncClient, db_session: AsyncSession
) -> None:
    owner = await user_id(client)
    other_plan = {"plan_code": "PLN_other", "interval": "monthly"}
    stranger = {"customer_code": "CUS_stranger", "email": "nobody@example.com"}
    payloads = [
        charge(owner, plan=other_plan),
        charge(owner, reference="ref_failed", status="failed"),
        charge(str(uuid.uuid4()), reference="ref_unknown_user"),
        event("subscription_create", subscription_code="SUB_x", customer=stranger),
        event("subscription_disable", subscription_code="SUB_unknown"),
        event("invoice_payment_failed", subscription={"subscription_code": "SUB_unknown"}),
        event("subscription_create", subscription_code="SUB_bad", customer="not an object"),
        {"event": "transfer.success", "data": {"reference": "trf_1"}},
    ]

    for payload in payloads:
        assert (await deliver(client, payload)).status_code == 200

    assert await recorded(db_session) == len(payloads)
    assert ((await state(client))[0], (await state(other_client))[0]) == ("free", "free")
    assert await db_session.scalar(select(func.count()).select_from(Subscription)) == 0


async def test_events_about_a_replaced_subscription_change_nothing(client: AsyncClient) -> None:
    owner = await user_id(client)
    await deliver(client, charge(owner))
    await deliver(client, event("subscription_create"))
    await deliver(client, event("subscription_disable"))

    # Upgrades again: a new charge and a new subscription.
    await deliver(client, charge(owner, reference="ref_checkout_2"))
    await deliver(client, event("subscription_create", subscription_code="SUB_ada_2"))
    # A late event about the old one.
    await deliver(client, event("invoice_payment_failed", invoice_code="INV_old"))

    plan, subscription = await state(client)
    assert (plan, subscription["status"]) == ("pro", "active")


async def test_a_signed_body_that_is_not_an_event(client: AsyncClient) -> None:
    response = await deliver(client, b'["not", "an", "event"]')

    assert response.status_code == 422


async def test_webhooks_need_billing_set_up(app: FastAPI, client: AsyncClient) -> None:
    del app.dependency_overrides[get_billing]

    response = await deliver(client, charge(uuid.uuid4()))

    assert response.status_code == 503


def test_event_keys() -> None:
    body = b"{}"
    assert event_key("charge.success", {"reference": "ref_1"}, body) == "charge.success:ref_1"
    assert (
        event_key("subscription.disable", {"subscription_code": "SUB_1"}, body)
        == "subscription.disable:SUB_1"
    )
    # A paid and an unpaid update of one invoice are different events.
    paid = event_key("invoice.update", {"invoice_code": "INV_1", "paid": True}, body)
    unpaid = event_key("invoice.update", {"invoice_code": "INV_1", "paid": False}, body)
    assert (paid, unpaid) == ("invoice.update:INV_1:true", "invoice.update:INV_1:false")
    # Events without a known id are keyed by their body.
    assert event_key("transfer.success", {"id": 1}, body).startswith("transfer.success:44136fa3")
    assert event_key("charge.success", {}, b"x") != event_key("charge.success", {}, b"y")
