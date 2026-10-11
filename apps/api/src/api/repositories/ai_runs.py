from datetime import datetime
from typing import Any

from sqlalchemy import func, select

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

    async def count_since(self, since: datetime, *, succeeded_only: bool) -> int:
        """Runs started at or after `since`; with `succeeded_only`, failed runs are left out."""
        stmt = (
            select(func.count()).select_from(AiRun).where(self._owner(), AiRun.created_at >= since)
        )
        if succeeded_only:
            stmt = stmt.where(AiRun.status == "succeeded")
        return await self.session.scalar(stmt) or 0
