"""Events from Paystack. No Firebase auth: the signature proves the sender."""

from typing import Annotated, Literal

from fastapi import APIRouter, Header, Request
from pydantic import BaseModel

from api.deps import BillingSetup, SubscriptionsFor, Users, Webhooks
from api.errors import ErrorEnvelope
from api.services import billing as service

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


class Received(BaseModel):
    status: Literal["ok"] = "ok"


@router.post(
    "/paystack",
    responses={
        401: {"model": ErrorEnvelope, "description": "The signature does not match"},
        503: {"model": ErrorEnvelope, "description": "Billing is not set up"},
    },
)
async def paystack(
    request: Request,
    billing: BillingSetup,
    webhooks: Webhooks,
    users: Users,
    subscriptions_for: SubscriptionsFor,
    x_paystack_signature: Annotated[str | None, Header()] = None,
) -> Received:
    await service.handle_webhook(
        billing,
        webhooks,
        users,
        subscriptions_for,
        body=await request.body(),
        signature=x_paystack_signature,
    )
    return Received()
