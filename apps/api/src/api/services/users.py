from api.ai.models import AiModel
from api.db.models import User
from api.errors import ValidationFailed
from api.ports.auth import Identity
from api.ports.llm.registry import ProviderRegistry
from api.ports.renderer import RendererClient
from api.repositories.users import UserRepository
from api.services.templates import require_template


async def ensure_user(users: UserRepository, identity: Identity) -> User:
    """The signed-in user's row, created on their first request."""
    return await users.get_or_create(identity.uid, identity.email)


async def update_me(
    users: UserRepository,
    renderer: RendererClient,
    providers: ProviderRegistry,
    user: User,
    *,
    display_name: str | None = None,
    preferred_ai_model: AiModel | None = None,
    default_template_id: str | None = None,
) -> User:
    values: dict[str, object] = {}
    if display_name is not None:
        values["display_name"] = display_name.strip() or None
    if preferred_ai_model is not None:
        if providers.option(preferred_ai_model) is None:
            raise ValidationFailed(
                "This AI model is not available on this server.", {"field": "preferred_ai_model"}
            )
        values["preferred_ai_model"] = str(preferred_ai_model)
    if default_template_id is not None:
        values["default_template_id"] = (await require_template(renderer, default_template_id)).id
    return await users.update(user, **values)
