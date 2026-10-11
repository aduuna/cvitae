"""Webhook bookkeeping, and the lookups that find whose subscription an event is about. One of the
two unscoped repositories: it returns user ids only; changes go through scoped repositories."""

import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.base import utcnow
from api.db.models import Subscription, WebhookEvent


class WebhookRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record(self, provider: str, event_key: str, event_type: str) -> bool:
        """Record an event; False when it was recorded before. A concurrent duplicate waits for
        the first delivery's transaction and then finds it."""
        inserted = await self.session.scalar(
            insert(WebhookEvent)
            .values(
                id=uuid.uuid4(),
                provider=provider,
                event_key=event_key,
                event_type=event_type,
                processed_at=utcnow(),
            )
            .on_conflict_do_nothing(index_elements=[WebhookEvent.event_key])
            .returning(WebhookEvent.id)
        )
        return inserted is not None

    async def subscription_owner(self, subscription_code: str) -> uuid.UUID | None:
        return await self.session.scalar(
            select(Subscription.user_id).where(
                Subscription.paystack_subscription_code == subscription_code
            )
        )

    async def customer_owner(self, customer_code: str) -> uuid.UUID | None:
        return await self.session.scalar(
            select(Subscription.user_id)
            .where(Subscription.paystack_customer_code == customer_code)
            .order_by(Subscription.updated_at.desc())
            .limit(1)
        )
