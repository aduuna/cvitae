from api.db.models import User
from api.ports.auth import Identity
from api.repositories.users import UserRepository


async def ensure_user(users: UserRepository, identity: Identity) -> User:
    """The signed-in user's row, created on their first request."""
    return await users.get_or_create(identity.uid, identity.email)
