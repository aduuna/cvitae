"""Browser extension tokens: the user's own list, and the lookup that finds a token's owner."""

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import ExtensionToken, User
from api.repositories.base import UserScopedRepository


class ExtensionTokenRepository(UserScopedRepository[ExtensionToken]):
    model = ExtensionToken

    async def list_recent(self) -> Sequence[ExtensionToken]:
        return await self.list(ExtensionToken.created_at.desc())

    async def least_recently_used(self) -> ExtensionToken | None:
        return await self.session.scalar(
            self._select()
            .order_by(
                ExtensionToken.last_used_at.asc().nulls_first(), ExtensionToken.created_at.asc()
            )
            .limit(1)
        )


class ExtensionTokenLookup:
    """Finds the user a token belongs to, before anyone is signed in. One of the unscoped
    repositories, like the users one: it reads a single token by its hash and nothing else."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def owner(self, token_hash: str) -> tuple[ExtensionToken, User] | None:
        row = (
            await self.session.execute(
                select(ExtensionToken, User)
                .join(User, User.id == ExtensionToken.user_id)
                .where(ExtensionToken.token_hash == token_hash, User.deleted_at.is_(None))
            )
        ).first()
        return (row[0], row[1]) if row else None

    async def touch(self, token_id: uuid.UUID, at: datetime) -> None:
        await self.session.execute(
            update(ExtensionToken).where(ExtensionToken.id == token_id).values(last_used_at=at)
        )
