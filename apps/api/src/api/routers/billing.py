"""Usage against the plan's limits, and upgrading to Pro with Paystack."""

from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from api.billing.plans import Plan
from api.deps import (
    AiRuns,
    BillingSetup,
    CurrentUser,
    Documents,
    Profiles,
    Subscriptions,
    UserPlan,
    Users,
    Webhooks,
)
from api.errors import ERROR_RESPONSES, ErrorEnvelope
from api.services import billing as service

router = APIRouter(tags=["billing"], responses=ERROR_RESPONSES)

UNAVAILABLE: dict[int | str, dict[str, Any]] = {
    503: {"model": ErrorEnvelope, "description": "Billing is not set up, or Paystack is down"}
}


class Meter(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    used: int
    limit: int
    message: str | None
    """Why no more can be made; set once the limit is reached."""


class SubscriptionInfo(BaseModel):
    status: Literal["active", "non_renewing", "attention", "cancelled"]
    current_period_end: datetime | None
    """Paid up to here."""
    manageable: bool
    """Whether Paystack's management page can be opened yet."""


class Usage(BaseModel):
    plan: Plan
    period_start: datetime
    period_end: datetime
    """When the AI runs reset (the start of the next calendar month, UTC)."""
    ai_runs: Meter
    documents: Meter
    profiles: Meter
    subscription: SubscriptionInfo | None


class Checkout(BaseModel):
    authorization_url: str
    """Paystack's checkout page; it sends the user back to /app/settings?tab=billing."""


class VerifyRequest(BaseModel):
    reference: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9._=-]+$")


class Verified(BaseModel):
    plan: Plan


class ManageLink(BaseModel):
    url: str


@router.get("/usage")
async def get_usage(
    plan: UserPlan,
    runs: AiRuns,
    documents: Documents,
    profiles: Profiles,
    subscriptions: Subscriptions,
) -> Usage:
    result = await service.overview(plan, runs, documents, profiles, subscriptions)
    usage, subscription = result.usage, result.subscription
    return Usage(
        plan=usage.plan,
        period_start=usage.period_start,
        period_end=usage.period_end,
        ai_runs=Meter.model_validate(usage.ai_runs),
        documents=Meter.model_validate(usage.documents),
        profiles=Meter.model_validate(usage.profiles),
        subscription=SubscriptionInfo.model_validate(
            {
                "status": subscription.status,
                "current_period_end": subscription.current_period_end,
                "manageable": subscription.paystack_subscription_code is not None,
            }
        )
        if subscription
        else None,
    )


@router.post("/billing/checkout", responses={409: {"model": ErrorEnvelope}, **UNAVAILABLE})
async def checkout(
    billing: BillingSetup, user: CurrentUser, plan: UserPlan, subscriptions: Subscriptions
) -> Checkout:
    """Start a Paystack checkout for the Pro plan."""
    url = await service.start_checkout(billing, subscriptions, user, plan)
    return Checkout(authorization_url=url)


@router.post("/billing/verify", responses=UNAVAILABLE)
async def verify(
    body: VerifyRequest,
    billing: BillingSetup,
    user: CurrentUser,
    webhooks: Webhooks,
    users: Users,
    subscriptions: Subscriptions,
) -> Verified:
    """Confirm a payment after Paystack sends the user back, and switch to Pro."""
    plan = await service.verify_checkout(
        billing, webhooks, users, subscriptions, user, body.reference
    )
    return Verified(plan=plan)


@router.get("/billing/manage-link", responses=UNAVAILABLE)
async def manage_link(billing: BillingSetup, subscriptions: Subscriptions) -> ManageLink:
    """Paystack's page for updating the card or cancelling."""
    return ManageLink(url=await service.manage_link(billing, subscriptions))
