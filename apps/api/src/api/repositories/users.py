"""Users are looked up by Firebase uid. One of the two unscoped repositories; keep it minimal."""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_or_create(self, firebase_uid: str, email: str) -> User:
        """The user for this uid, created on first sight. Keeps the email current."""
        user = await self._by_uid(firebase_uid)
        if user is None:
            # Two first requests can race; the loser's insert does nothing.
            await self.session.execute(
                insert(User)
                .values(firebase_uid=firebase_uid, email=email)
                .on_conflict_do_nothing(index_elements=[User.firebase_uid])
            )
            user = await self._by_uid(firebase_uid)
            assert user is not None  # noqa: S101 - inserted or found above
        elif user.email != email:
            user.email = email
            await self.session.flush()
        return user

    async def _by_uid(self, firebase_uid: str) -> User | None:
        return await self.session.scalar(select(User).where(User.firebase_uid == firebase_uid))

    async def update(self, user: User, **values: object) -> User:
        for name, value in values.items():
            setattr(user, name, value)
        await self.session.flush()
        return user
