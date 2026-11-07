from collections.abc import Sequence

from sqlalchemy import delete, func, select

from api.db.models import UserTemplate
from api.repositories.base import UserScopedRepository


class UserTemplateRepository(UserScopedRepository[UserTemplate]):
    model = UserTemplate

    async def count(self) -> int:
        """Templates the user can use: drafts are not counted, so an unconfirmed one never
        takes the place of a template (the plan limit reads this)."""
        stmt = (
            select(func.count())
            .select_from(UserTemplate)
            .where(self._owner(), UserTemplate.status == "ready")
        )
        return await self.session.scalar(stmt) or 0

    async def list_ready(self) -> Sequence[UserTemplate]:
        """The user's templates in the order they were made."""
        result = await self.session.scalars(
            self._select()
            .where(UserTemplate.status == "ready")
            .order_by(UserTemplate.created_at, UserTemplate.id)
        )
        return result.all()

    async def get_by_slug(self, slug: str) -> UserTemplate | None:
        """One of the user's templates, draft or ready, by its template id."""
        return await self.session.scalar(self._select().where(UserTemplate.slug == slug))

    async def delete_drafts(self) -> None:
        """Remove the user's unconfirmed generations."""
        await self.session.execute(
            delete(UserTemplate).where(self._owner(), UserTemplate.status == "draft")
        )
