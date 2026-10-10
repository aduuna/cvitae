from collections.abc import Sequence

from api.db.models import Job
from api.repositories.base import UserScopedRepository


class JobRepository(UserScopedRepository[Job]):
    model = Job

    async def list_recent(self) -> Sequence[Job]:
        return await self.list(Job.updated_at.desc())
