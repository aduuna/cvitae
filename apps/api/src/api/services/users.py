from typing import Literal

from api.db.models import User
from api.ports.auth import Identity
from api.ports.renderer import RendererClient
from api.repositories.users import UserRepository
from api.services.templates import require_template


async def ensure_user(users: UserRepository, identity: Identity) -> User:
    """The signed-in user's row, created on their first request."""
    return await users.get_or_create(identity.uid, identity.email)


async def update_me(
    users: UserRepository,
    renderer: RendererClient,
    user: User,
    *,
    display_name: str | None = None,
    preferred_provider: Literal["claude", "gemini"] | None = None,
    default_template_id: str | None = None,
) -> User:
    values: dict[str, object] = {}
    if display_name is not None:
        values["display_name"] = display_name.strip() or None
    if preferred_provider is not None:
        values["preferred_provider"] = preferred_provider
    if default_template_id is not None:
        values["default_template_id"] = (await require_template(renderer, default_template_id)).id
    return await users.update(user, **values)
