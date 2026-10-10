"""UserScopedRepository: every query is limited to one user's rows."""

import uuid
from collections.abc import Sequence
from typing import Any, ClassVar

from sqlalchemy import ColumnElement, Select, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.base import Entity


class UserScopedRepository[M: Entity]:
    """Data access for one model, scoped to `user_id` given at construction. Subclasses build
    queries from `_select()` or `_owner()` only, so no query can reach another user's rows."""

    model: ClassVar[type[Any]]

    def __init__(self, session: AsyncSession, user_id: uuid.UUID) -> None:
        self.session = session
        self.user_id = user_id

    def _owner(self) -> ColumnElement[bool]:
        """The ownership condition. Default: the model's own `user_id` column."""
        return self.model.__table__.c.user_id == self.user_id

    def _select(self) -> Select[M]:
        return select(self.model).where(self._owner())

    async def get(self, id: uuid.UUID) -> M | None:
        return await self.session.scalar(self._select().where(self.model.id == id))

    async def list(self, *order_by: ColumnElement[Any]) -> Sequence[M]:
        result = await self.session.scalars(self._select().order_by(*order_by))
        return result.all()

    async def count(self) -> int:
        stmt = select(func.count()).select_from(self.model).where(self._owner())
        return await self.session.scalar(stmt) or 0

    async def create(self, **values: Any) -> M:
        row: M = self.model(user_id=self.user_id, **values)
        self.session.add(row)
        await self.session.flush()
        return row

    async def update(self, row: M, **values: Any) -> M:
        """Change a row obtained from `get` or `list`."""
        for name, value in values.items():
            setattr(row, name, value)
        await self.session.flush()
        return row

    async def update_where(self, *criteria: ColumnElement[bool], **values: Any) -> None:
        """Bulk update of the user's rows that match `criteria`."""
        stmt = update(self.model).where(self._owner(), *criteria).values(**values)
        await self.session.execute(stmt)

    async def delete(self, id: uuid.UUID) -> bool:
        """Delete one of the user's rows; False when there is no such row."""
        stmt = delete(self.model).where(self._owner(), self.model.id == id)
        result = await self.session.execute(stmt)
        return bool(getattr(result, "rowcount", 0))
