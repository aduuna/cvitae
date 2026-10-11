from typing import Any

from api.db.models import Subscription
from api.repositories.base import UserScopedRepository


class SubscriptionRepository(UserScopedRepository[Subscription]):
    """The user's one subscription row."""

    model = Subscription

    async def current(self) -> Subscription | None:
        return await self.session.scalar(self._select())

    async def save(self, **values: Any) -> Subscription:
        """Create the row, or change the existing one."""
        row = await self.current()
        if row is None:
            return await self.create(**values)
        return await self.update(row, **values)
