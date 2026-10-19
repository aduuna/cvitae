from collections.abc import Sequence

from api.db.models import Job
from api.repositories.base import UserScopedRepository


class JobRepository(UserScopedRepository[Job]):
    model = Job

    async def list_recent(self) -> Sequence[Job]:
        return await self.list(Job.updated_at.desc())

    async def get_by_url(self, url: str) -> Job | None:
        """The most recent job saved from this URL."""
        return await self.session.scalar(
            self._select().where(Job.url == url).order_by(Job.created_at.desc()).limit(1)
        )
