"""The Paystack client against a mocked API, and webhook signatures."""

import hashlib
import hmac
import json
import uuid

import httpx
import pytest
import respx

from api.errors import NotFound, ServiceUnavailable
from api.ports.billing import BASE_URL, HttpPaystackClient, Transaction, sign

SECRET = "sk_test_secret"  # noqa: S105 - test key
PLAN = "PLN_pro_test"
USER = uuid.UUID("6f1c1c1e-0000-4000-8000-000000000001")


def ok(data: object) -> httpx.Response:
    return httpx.Response(200, json={"status": True, "message": "ok", "data": data})


def client() -> HttpPaystackClient:
    return HttpPaystackClient(SECRET)


@respx.mock
async def test_checkout_subscribes_to_the_plan_with_its_own_amount() -> None:
    plan = respx.get(f"{BASE_URL}/plan/{PLAN}").mock(
        return_value=ok({"plan_code": PLAN, "amount": 500000, "currency": "GHS"})
    )
    init = respx.post(f"{BASE_URL}/transaction/initialize").mock(
        return_value=ok(
            {
                "authorization_url": "https://checkout.paystack.com/abc",
                "access_code": "abc",
                "reference": "ref_1",
            }
        )
    )
    paystack = client()

    for _ in range(2):
        checkout = await paystack.initialize(
            email="ada@example.com",
            plan_code=PLAN,
            callback_url="https://app.test/app/settings?tab=billing",
            metadata={"user_id": str(USER)},
        )

    assert (checkout.authorization_url, checkout.reference) == (
        "https://checkout.paystack.com/abc",
        "ref_1",
    )
    # The plan's amount is fetched once.
    assert plan.call_count == 1
    sent = init.calls[0].request
    assert sent.headers["Authorization"] == f"Bearer {SECRET}"
    assert json.loads(sent.content) == {
        "email": "ada@example.com",
        "amount": 500000,
        "plan": PLAN,
        "callback_url": "https://app.test/app/settings?tab=billing",
        "metadata": {"user_id": str(USER)},
    }


@respx.mock
async def test_verify_reads_the_customer_plan_and_metadata() -> None:
    respx.get(f"{BASE_URL}/transaction/verify/ref_1").mock(
        return_value=ok(
            {
                "status": "success",
                "reference": "ref_1",
                "amount": 500000,
                # Paystack may return metadata as a JSON string, and the plan as a bare code.
                "metadata": json.dumps({"user_id": str(USER)}),
                "customer": {"customer_code": "CUS_ada", "email": "ada@example.com", "id": 1},
                "plan": PLAN,
            }
        )
    )

    transaction = await client().verify("ref_1")

    assert (transaction.status, transaction.plan_code, transaction.user_id) == (
        "success",
        PLAN,
        USER,
    )
    assert transaction.customer.customer_code == "CUS_ada"


def test_transactions_without_a_plan_or_our_metadata() -> None:
    one_off = Transaction.model_validate(
        {
            "status": "success",
            "reference": "r",
            "customer": {"customer_code": "CUS_x"},
            "plan": {},
            "metadata": "not json",
        }
    )
    renewal = Transaction.model_validate(
        {
            "status": "success",
            "reference": "r2",
            "customer": {"customer_code": "CUS_x"},
            "plan": {},
            "plan_object": {"plan_code": PLAN},
            "metadata": {"invoice_action": "create"},
        }
    )

    assert (one_off.plan_code, one_off.metadata, one_off.user_id) == (None, {}, None)
    assert (renewal.plan_code, renewal.user_id) == (PLAN, None)


@respx.mock
async def test_unknown_references_and_subscriptions_are_not_found() -> None:
    respx.get(f"{BASE_URL}/transaction/verify/nope").mock(
        return_value=httpx.Response(
            400, json={"status": False, "message": "Transaction reference not found"}
        )
    )
    respx.get(f"{BASE_URL}/subscription/SUB_gone/manage/link").mock(
        return_value=httpx.Response(404, json={"status": False, "message": "Not found"})
    )

    with pytest.raises(NotFound):
        await client().verify("nope")
    with pytest.raises(NotFound):
        await client().manage_link("SUB_gone")


@respx.mock
async def test_manage_link() -> None:
    link = "https://paystack.com/manage/subscriptions/qlgwhpyq1ts9nsw?subscription_token=t"
    respx.get(f"{BASE_URL}/subscription/SUB_ada/manage/link").mock(return_value=ok({"link": link}))

    assert await client().manage_link("SUB_ada") == link


@respx.mock
async def test_paystack_failures_are_service_unavailable() -> None:
    respx.get(f"{BASE_URL}/plan/{PLAN}").mock(
        return_value=httpx.Response(400, json={"status": False, "message": "Plan not found"})
    )
    respx.get(f"{BASE_URL}/transaction/verify/ref_1").mock(side_effect=httpx.ConnectError("down"))
    respx.get(f"{BASE_URL}/subscription/SUB_ada/manage/link").mock(
        return_value=httpx.Response(502, text="Bad gateway")
    )
    paystack = client()

    with pytest.raises(ServiceUnavailable, match="could not handle"):
        await paystack.initialize(email="a@x.com", plan_code=PLAN, callback_url="u", metadata={})
    with pytest.raises(ServiceUnavailable, match="not reachable"):
        await paystack.verify("ref_1")
    with pytest.raises(ServiceUnavailable, match="could not handle"):
        await paystack.manage_link("SUB_ada")


def test_signatures_are_hmac_sha512_of_the_raw_body() -> None:
    body = b'{"event":"charge.success","data":{}}'
    expected = hmac.new(SECRET.encode(), body, hashlib.sha512).hexdigest()
    paystack = client()

    assert sign(SECRET, body) == expected
    assert paystack.signature_valid(body, expected)
    assert not paystack.signature_valid(body + b" ", expected)
    assert not paystack.signature_valid(body, sign("sk_test_other", body))
    assert not paystack.signature_valid(body, None)
    assert not paystack.signature_valid(body, "")
