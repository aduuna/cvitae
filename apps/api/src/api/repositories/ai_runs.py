from typing import Any

from api.db.models import AiRun
from api.repositories.base import UserScopedRepository


class AiRunRepository(UserScopedRepository[AiRun]):
    model = AiRun

    async def checkpoint(self) -> None:
        """Commit the request's work so far, before a long AI call: the call does not hold a
        transaction or a pooled connection, and the user row exists for the run record."""
        await self.session.commit()

    async def record(self, **values: Any) -> AiRun:
        """Add a run and commit it at once: a failed run must survive the error response."""
        run = await self.create(**values)
        await self.session.commit()
        return run
