from collections.abc import Sequence

from api.db.models import Upload
from api.repositories.base import UserScopedRepository


class UploadRepository(UserScopedRepository[Upload]):
    model = Upload

    async def list_recent(self) -> Sequence[Upload]:
        return await self.list(Upload.created_at.desc())
