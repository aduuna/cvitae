import uuid
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from api.ai.models import AiModel
from api.deps import CurrentUser, Providers, Renderer, Users
from api.errors import ERROR_RESPONSES
from api.services import users as service

router = APIRouter(prefix="/me", tags=["me"], responses=ERROR_RESPONSES)


class Me(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str | None
    preferred_ai_model: AiModel | None
    """The model the user chose, if it is still offered; None means the server's default."""
    plan: Literal["free", "pro"]
    default_template_id: str | None


class MeUpdate(BaseModel):
    display_name: str | None = Field(None, max_length=200)
    preferred_ai_model: AiModel | None = None
    default_template_id: str | None = Field(None, min_length=1, max_length=64)


def me(user: object, providers: Providers) -> Me:
    result = Me.model_validate(user)
    if result.preferred_ai_model and not providers.option(result.preferred_ai_model):
        result.preferred_ai_model = None
    return result


@router.get("")
async def get_me(user: CurrentUser, providers: Providers) -> Me:
    return me(user, providers)


@router.patch("")
async def update_me(
    body: MeUpdate, user: CurrentUser, users: Users, renderer: Renderer, providers: Providers
) -> Me:
    row = await service.update_me(
        users,
        renderer,
        providers,
        user,
        display_name=body.display_name,
        preferred_ai_model=body.preferred_ai_model,
        default_template_id=body.default_template_id,
    )
    return me(row, providers)
