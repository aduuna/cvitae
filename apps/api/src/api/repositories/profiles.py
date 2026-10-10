from collections.abc import Sequence

from api.db.models import Profile
from api.repositories.base import UserScopedRepository


class ProfileRepository(UserScopedRepository[Profile]):
    model = Profile

    async def list_recent(self) -> Sequence[Profile]:
        return await self.list(Profile.updated_at.desc())

    async def clear_default(self) -> None:
        await self.update_where(Profile.is_default.is_(True), is_default=False)
