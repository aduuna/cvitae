"""The Paystack port: checkout, payment verification, the subscription management link and webhook
signatures (docs/BACKEND.md, Billing). Payload models follow Paystack's documented samples and
ignore fields they do not need."""

import hashlib
import hmac
import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

import httpx
from pydantic import BaseModel, ConfigDict, model_validator

from api.errors import NotFound, ServiceUnavailable

logger = logging.getLogger(__name__)

BASE_URL = "https://api.paystack.co"
TIMEOUT_SECONDS = 15

UNAVAILABLE = "Paystack is not reachable right now. Try again in a moment."


def sign(secret: str, body: bytes) -> str:
    """Paystack's `x-paystack-signature`: HMAC SHA512 of the raw body, hex encoded."""
    return hmac.new(secret.encode(), body, hashlib.sha512).hexdigest()


def signature_matches(secret: str, body: bytes, signature: str | None) -> bool:
    return bool(signature) and hmac.compare_digest(sign(secret, body), signature or "")


def _plan_code(value: object) -> str | None:
    """A plan arrives as an object, a bare plan code, or an empty object for one-off charges."""
    if isinstance(value, dict):
        code = value.get("plan_code")
        return code if isinstance(code, str) and code else None
    return value if isinstance(value, str) and value else None


class _Payload(BaseModel):
    model_config = ConfigDict(extra="ignore")


class Customer(_Payload):
    customer_code: str
    email: str = ""


class Transaction(_Payload):
    """A transaction, as verify returns it and charge.success sends it."""

    reference: str
    status: str
    customer: Customer
    plan_code: str | None = None
    metadata: dict[str, Any] = {}

    @model_validator(mode="before")
    @classmethod
    def _normalise(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        data = dict(data)
        if "plan_code" not in data:
            data["plan_code"] = _plan_code(data.get("plan")) or _plan_code(data.get("plan_object"))
        # Metadata comes back as the object that was sent, or as a JSON string.
        metadata = data.get("metadata")
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except ValueError:
                metadata = None
        data["metadata"] = metadata if isinstance(metadata, dict) else {}
        return data

    @property
    def user_id(self) -> uuid.UUID | None:
        """The user who started the checkout, from the metadata the api sent."""
        try:
            return uuid.UUID(str(self.metadata.get("user_id")))
        except ValueError:
            return None


class SubscriptionData(_Payload):
    """subscription.create, subscription.not_renew and subscription.disable."""

    subscription_code: str
    status: str
    customer: Customer
    plan_code: str | None = None
    next_payment_date: datetime | None = None

    @model_validator(mode="before")
    @classmethod
    def _normalise(cls, data: Any) -> Any:
        if isinstance(data, dict) and "plan_code" not in data:
            data = {**data, "plan_code": _plan_code(data.get("plan"))}
        return data


class InvoiceSubscription(_Payload):
    subscription_code: str
    next_payment_date: datetime | None = None


class Invoice(_Payload):
    """invoice.update and invoice.payment_failed."""

    invoice_code: str
    paid: bool = False
    subscription: InvoiceSubscription


@dataclass(frozen=True)
class Checkout:
    authorization_url: str
    reference: str


class PaystackClient(Protocol):
    async def initialize(
        self, *, email: str, plan_code: str, callback_url: str, metadata: dict[str, str]
    ) -> Checkout:
        """Start a checkout that subscribes the customer to `plan_code`."""
        ...

    async def verify(self, reference: str) -> Transaction: ...

    async def manage_link(self, subscription_code: str) -> str:
        """A Paystack-hosted page where the customer updates their card or cancels."""
        ...

    def signature_valid(self, body: bytes, signature: str | None) -> bool: ...


class HttpPaystackClient:
    """Paystack's REST API with the secret key. No retries: every call is a user action that the
    user can repeat, and webhooks are retried by Paystack."""

    def __init__(
        self, secret_key: str, *, base_url: str = BASE_URL, client: httpx.AsyncClient | None = None
    ) -> None:
        self._secret = secret_key
        self._client = client or httpx.AsyncClient(base_url=base_url, timeout=TIMEOUT_SECONDS)
        self._plan_amounts: dict[str, int] = {}

    async def aclose(self) -> None:
        await self._client.aclose()

    def signature_valid(self, body: bytes, signature: str | None) -> bool:
        return signature_matches(self._secret, body, signature)

    async def _call(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        headers = {"Authorization": f"Bearer {self._secret}"}
        try:
            return await self._client.request(method, path, headers=headers, **kwargs)
        except httpx.TransportError as exc:
            logger.warning("paystack unreachable", extra={"reason": type(exc).__name__})
            raise ServiceUnavailable(UNAVAILABLE) from exc

    def _data(self, response: httpx.Response, operation: str) -> dict[str, Any]:
        body = _json(response)
        if (
            response.is_success
            and body.get("status") is True
            and isinstance(body.get("data"), dict)
        ):
            return body["data"]
        # Paystack's message names the problem (for example an unknown plan); it holds no
        # customer data.
        logger.warning(
            "paystack call failed",
            extra={
                "operation": operation,
                "status": response.status_code,
                "reason": body.get("message"),
            },
        )
        raise ServiceUnavailable("Paystack could not handle this request. Try again later.")

    async def _plan_amount(self, plan_code: str) -> int:
        """Initialize needs an amount even with a plan, which overrides it: send the plan's own."""
        if plan_code not in self._plan_amounts:
            response = await self._call("GET", f"/plan/{plan_code}")
            self._plan_amounts[plan_code] = int(self._data(response, "fetch_plan")["amount"])
        return self._plan_amounts[plan_code]

    async def initialize(
        self, *, email: str, plan_code: str, callback_url: str, metadata: dict[str, str]
    ) -> Checkout:
        body = {
            "email": email,
            "amount": await self._plan_amount(plan_code),
            "plan": plan_code,
            "callback_url": callback_url,
            "metadata": metadata,
        }
        data = self._data(await self._call("POST", "/transaction/initialize", json=body), "init")
        return Checkout(authorization_url=data["authorization_url"], reference=data["reference"])

    async def verify(self, reference: str) -> Transaction:
        response = await self._call("GET", f"/transaction/verify/{reference}")
        if response.status_code in (400, 404):
            raise NotFound("Paystack has no payment with this reference.")
        return Transaction.model_validate(self._data(response, "verify"))

    async def manage_link(self, subscription_code: str) -> str:
        response = await self._call("GET", f"/subscription/{subscription_code}/manage/link")
        if response.status_code in (400, 404):
            raise NotFound("Paystack no longer has this subscription.")
        return str(self._data(response, "manage_link")["link"])


def _json(response: httpx.Response) -> dict[str, Any]:
    try:
        body = response.json()
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}


class FakePaystackClient:
    """In-memory Paystack for tests and local work: checkouts complete with `pay`."""

    SECRET = "sk_test_fake"  # noqa: S105 - signs test webhooks only

    def __init__(self) -> None:
        self.checkouts: list[dict[str, Any]] = []
        self.transactions: dict[str, Transaction] = {}
        self.manage_links: list[str] = []

    def signature_valid(self, body: bytes, signature: str | None) -> bool:
        return signature_matches(self.SECRET, body, signature)

    async def initialize(
        self, *, email: str, plan_code: str, callback_url: str, metadata: dict[str, str]
    ) -> Checkout:
        reference = f"ref_{len(self.checkouts) + 1}"
        self.checkouts.append(
            {
                "email": email,
                "plan_code": plan_code,
                "callback_url": callback_url,
                "metadata": metadata,
                "reference": reference,
            }
        )
        self.transactions[reference] = Transaction(
            reference=reference,
            status="abandoned",
            customer=Customer(customer_code=f"CUS_{len(self.checkouts)}", email=email),
            plan_code=plan_code,
            metadata=dict(metadata),
        )
        return Checkout(f"https://checkout.paystack.test/{reference}", reference)

    def pay(self, reference: str) -> Transaction:
        """The customer completes the checkout."""
        paid = self.transactions[reference].model_copy(update={"status": "success"})
        self.transactions[reference] = paid
        return paid

    async def verify(self, reference: str) -> Transaction:
        if reference not in self.transactions:
            raise NotFound("Paystack has no payment with this reference.")
        return self.transactions[reference]

    async def manage_link(self, subscription_code: str) -> str:
        self.manage_links.append(subscription_code)
        return f"https://paystack.test/manage/subscriptions/{subscription_code}"
