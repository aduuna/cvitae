"""Billing with Paystack (docs/BACKEND.md, Billing): the plan a user is on, checkout and its
verification, the management link, and the webhook events that keep `subscriptions` and
`users.plan` in step with Paystack. Event bodies are never logged; ids and event types are."""

import hashlib
import json
import logging
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pydantic import ValidationError

from api.billing.plans import Plan
from api.db.base import utcnow
from api.db.models import Subscription, User
from api.errors import Conflict, NotFound, Unauthorized, ValidationFailed
from api.ports.billing import Invoice, PaystackClient, SubscriptionData, Transaction
from api.repositories.ai_runs import AiRunRepository
from api.repositories.documents import DocumentRepository
from api.repositories.profiles import ProfileRepository
from api.repositories.subscriptions import SubscriptionRepository
from api.repositories.users import UserRepository
from api.repositories.webhooks import WebhookRepository
from api.services import quotas

logger = logging.getLogger(__name__)

PROVIDER = "paystack"

# Paystack's subscription statuses, as stored in subscriptions.status.
_STATUSES = {
    "active": "active",
    "non-renewing": "non_renewing",
    "attention": "attention",
    "complete": "cancelled",
    "completed": "cancelled",
    "cancelled": "cancelled",
}


@dataclass(frozen=True)
class Billing:
    """Paystack and the Pro plan this server sells; absent when billing is not set up."""

    client: PaystackClient
    plan_code: str
    callback_url: str


@dataclass(frozen=True)
class Overview:
    usage: quotas.Usage
    subscription: Subscription | None


type SubscriptionsFor = Callable[[uuid.UUID], SubscriptionRepository]
"""The subscription repository scoped to one user, for events about that user."""


def effective_plan(user: User, subscription: Subscription | None, now: datetime) -> Plan:
    """`users.plan`, except that a subscription whose renewal failed ends at the period it was
    paid up to. Paystack may never disable such a subscription, so this needs no event."""
    if user.plan != "pro":
        return "free"
    if (
        subscription is not None
        and subscription.status == "attention"
        and subscription.current_period_end is not None
        and subscription.current_period_end <= now
    ):
        return "free"
    return "pro"


async def current_plan(
    user: User, subscriptions: SubscriptionRepository, *, now: datetime | None = None
) -> Plan:
    if user.plan != "pro":
        return "free"
    return effective_plan(user, await subscriptions.current(), now or utcnow())


async def overview(
    plan: Plan,
    runs: AiRunRepository,
    documents: DocumentRepository,
    profiles: ProfileRepository,
    subscriptions: SubscriptionRepository,
) -> Overview:
    return Overview(
        usage=await quotas.usage(plan, runs, documents, profiles),
        subscription=await subscriptions.current(),
    )


async def start_checkout(
    billing: Billing, subscriptions: SubscriptionRepository, user: User, plan: Plan
) -> str:
    """A Paystack checkout for the Pro plan; returns the page to send the user to."""
    if plan == "pro":
        raise Conflict("You are already on Pro.")
    subscription = await subscriptions.current()
    if subscription is not None and subscription.status == "attention":
        # Paying again would start a second subscription next to the one waiting for a card.
        raise Conflict(
            "Your last payment did not go through. Update your card from Manage subscription "
            "to get Pro back."
        )
    checkout = await billing.client.initialize(
        email=user.email,
        plan_code=billing.plan_code,
        callback_url=billing.callback_url,
        metadata={"user_id": str(user.id)},
    )
    logger.info("checkout started", extra={"user_id": str(user.id)})
    return checkout.authorization_url


async def _activate(
    users: UserRepository,
    subscriptions: SubscriptionRepository,
    transaction: Transaction,
) -> None:
    """A paid Pro charge: the user is on Pro, with Paystack's customer on record."""
    await subscriptions.save(
        paystack_customer_code=transaction.customer.customer_code,
        plan_code=transaction.plan_code,
        status="active",
    )
    await users.set_plan(subscriptions.user_id, "pro")


async def verify_checkout(
    billing: Billing,
    webhooks: WebhookRepository,
    users: UserRepository,
    subscriptions: SubscriptionRepository,
    user: User,
    reference: str,
) -> Plan:
    """After Paystack sends the user back: confirm the payment and switch to Pro at once, without
    waiting for the webhook. Safe to repeat: a payment is applied once, here or by its
    charge.success webhook, so an old reference cannot bring Pro back after it ended."""
    transaction = await billing.client.verify(reference)
    if transaction.user_id != user.id:
        raise NotFound("Paystack has no payment with this reference.")
    if transaction.status != "success":
        raise ValidationFailed(
            "Paystack has not confirmed this payment. If you paid, reload this page in a minute."
        )
    if transaction.plan_code != billing.plan_code:
        raise ValidationFailed("This payment is not for the Pro plan.")
    key = event_key("charge.success", {"reference": transaction.reference}, b"")
    if await webhooks.record(PROVIDER, key, "charge.success"):
        await _activate(users, subscriptions, transaction)
        logger.info("checkout verified", extra={"user_id": str(user.id)})
    return await current_plan(user, subscriptions)


async def manage_link(billing: Billing, subscriptions: SubscriptionRepository) -> str:
    subscription = await subscriptions.current()
    if subscription is None or subscription.paystack_subscription_code is None:
        raise NotFound("There is no subscription to manage yet.")
    return await billing.client.manage_link(subscription.paystack_subscription_code)


def event_key(event: str, data: Any, body: bytes) -> str:
    """What makes an event the same event when Paystack delivers it again. A paid and an unpaid
    update of one invoice are different events."""
    fields: dict[str, tuple[str, ...]] = {
        "charge.success": ("reference",),
        "subscription.create": ("subscription_code",),
        "subscription.not_renew": ("subscription_code",),
        "subscription.disable": ("subscription_code",),
        "invoice.update": ("invoice_code", "paid"),
        "invoice.payment_failed": ("invoice_code",),
    }
    names = fields.get(event, ())
    values = [data.get(name) for name in names] if isinstance(data, dict) else []
    if values and all(value is not None and value != "" for value in values):
        parts = (str(v).lower() if isinstance(v, bool) else str(v) for v in values)
        return f"{event}:{':'.join(parts)}"[:255]
    return f"{event}:{hashlib.sha256(body).hexdigest()}"


@dataclass(frozen=True)
class _Context:
    billing: Billing
    webhooks: WebhookRepository
    users: UserRepository
    subscriptions_for: SubscriptionsFor


async def _charge_success(context: _Context, data: dict[str, Any]) -> uuid.UUID | None:
    transaction = Transaction.model_validate(data)
    if transaction.status != "success" or transaction.plan_code != context.billing.plan_code:
        return None
    owner = transaction.user_id
    if owner is None or await context.users.get(owner) is None:
        # Renewals carry no metadata of ours; the customer is already on record.
        owner = await context.webhooks.customer_owner(transaction.customer.customer_code)
    if owner is None:
        return None
    await _activate(context.users, context.subscriptions_for(owner), transaction)
    return owner


async def _subscription_create(context: _Context, data: dict[str, Any]) -> uuid.UUID | None:
    subscription = SubscriptionData.model_validate(data)
    if subscription.plan_code != context.billing.plan_code:
        return None
    owner = await context.webhooks.subscription_owner(
        subscription.subscription_code
    ) or await context.webhooks.customer_owner(subscription.customer.customer_code)
    if owner is None:
        # This can arrive before charge.success. Checkout used the account's email.
        user = await context.users.only_with_email(subscription.customer.email)
        owner = user.id if user else None
    if owner is None:
        return None
    status = _STATUSES.get(subscription.status, "active")
    await context.subscriptions_for(owner).save(
        paystack_customer_code=subscription.customer.customer_code,
        paystack_subscription_code=subscription.subscription_code,
        plan_code=subscription.plan_code,
        status=status,
        current_period_end=subscription.next_payment_date,
    )
    await context.users.set_plan(owner, "free" if status == "cancelled" else "pro")
    return owner


async def _subscription_change(
    context: _Context, subscription_code: str, **values: Any
) -> uuid.UUID | None:
    """Change the subscription with this code. Events about a subscription the user has since
    replaced, or one that has ended, change nothing."""
    owner = await context.webhooks.subscription_owner(subscription_code)
    if owner is None:
        return None
    subscriptions = context.subscriptions_for(owner)
    current = await subscriptions.current()
    if current is None or current.status == "cancelled":
        return None
    await subscriptions.save(**values)
    return owner


async def _invoice_update(context: _Context, data: dict[str, Any]) -> uuid.UUID | None:
    """A renewal was paid: Pro continues to the new next payment date."""
    invoice = Invoice.model_validate(data)
    if not invoice.paid:
        return None
    values: dict[str, Any] = {"status": "active"}
    if invoice.subscription.next_payment_date is not None:
        values["current_period_end"] = invoice.subscription.next_payment_date
    owner = await _subscription_change(context, invoice.subscription.subscription_code, **values)
    if owner is not None:
        await context.users.set_plan(owner, "pro")
    return owner


async def _payment_failed(context: _Context, data: dict[str, Any]) -> uuid.UUID | None:
    """A renewal failed: Pro stays until the paid period ends (see effective_plan)."""
    invoice = Invoice.model_validate(data)
    return await _subscription_change(
        context, invoice.subscription.subscription_code, status="attention"
    )


async def _not_renew(context: _Context, data: dict[str, Any]) -> uuid.UUID | None:
    """Cancelled: Pro stays until Paystack disables the subscription at the period end."""
    subscription = SubscriptionData.model_validate(data)
    return await _subscription_change(
        context, subscription.subscription_code, status="non_renewing"
    )


async def _disable(context: _Context, data: dict[str, Any]) -> uuid.UUID | None:
    subscription = SubscriptionData.model_validate(data)
    owner = await _subscription_change(context, subscription.subscription_code, status="cancelled")
    if owner is not None:
        await context.users.set_plan(owner, "free")
    return owner


_HANDLERS: dict[str, Callable[[_Context, dict[str, Any]], Awaitable[uuid.UUID | None]]] = {
    "charge.success": _charge_success,
    "subscription.create": _subscription_create,
    "invoice.update": _invoice_update,
    "invoice.payment_failed": _payment_failed,
    "subscription.not_renew": _not_renew,
    "subscription.disable": _disable,
}


async def handle_webhook(
    billing: Billing,
    webhooks: WebhookRepository,
    users: UserRepository,
    subscriptions_for: SubscriptionsFor,
    *,
    body: bytes,
    signature: str | None,
) -> None:
    """Check the signature, skip an event seen before, and apply the event. Events this app does
    not use, or about customers it does not know, are recorded and otherwise ignored."""
    if not billing.client.signature_valid(body, signature):
        logger.warning("paystack webhook with an invalid signature")
        raise Unauthorized("The webhook signature is not valid.")
    try:
        payload = json.loads(body)
        event, data = str(payload["event"]), payload["data"]
    except (ValueError, KeyError, TypeError) as exc:
        logger.warning("paystack webhook is not an event")
        raise ValidationFailed("The webhook body is not a Paystack event.") from exc

    key = event_key(event, data, body)
    if not await webhooks.record(PROVIDER, key, event):
        logger.info("paystack webhook repeated", extra={"event": event, "event_key": key})
        return
    handler = _HANDLERS.get(event)
    owner = None
    if handler is not None:
        context = _Context(billing, webhooks, users, subscriptions_for)
        try:
            owner = await handler(context, data)
        except ValidationError:
            logger.warning("paystack event not understood", extra={"event": event})
            return
    logger.info(
        "paystack webhook",
        extra={
            "event": event,
            "event_key": key,
            "handled": owner is not None,
            "user_id": str(owner) if owner else None,
        },
    )
