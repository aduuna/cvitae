import uuid
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from api.deps import CurrentUser, Renderer, Users
from api.errors import ERROR_RESPONSES
from api.services import users as service

router = APIRouter(prefix="/me", tags=["me"], responses=ERROR_RESPONSES)


class Me(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str | None
    preferred_provider: Literal["claude", "gemini"]
    plan: Literal["free", "pro"]
    default_template_id: str | None


class MeUpdate(BaseModel):
    display_name: str | None = Field(None, max_length=200)
    preferred_provider: Literal["claude", "gemini"] | None = None
    default_template_id: str | None = Field(None, min_length=1, max_length=64)


@router.get("")
async def get_me(user: CurrentUser) -> Me:
    return Me.model_validate(user)


@router.patch("")
async def update_me(body: MeUpdate, user: CurrentUser, users: Users, renderer: Renderer) -> Me:
    row = await service.update_me(
        users,
        renderer,
        user,
        display_name=body.display_name,
        preferred_provider=body.preferred_provider,
        default_template_id=body.default_template_id,
    )
    return Me.model_validate(row)
