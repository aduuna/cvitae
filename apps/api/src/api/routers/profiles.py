import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, status
from pydantic import BaseModel, ConfigDict, Field

from api.deps import Profiles
from api.errors import ERROR_RESPONSES
from api.services import profiles as service
from cvcore.models import CvContent

router = APIRouter(prefix="/profiles", tags=["profiles"], responses=ERROR_RESPONSES)

Name = Field(min_length=1, max_length=200)


class ProfileSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    is_default: bool
    created_at: datetime
    updated_at: datetime


class Profile(ProfileSummary):
    content: CvContent


class ProfileCreate(BaseModel):
    name: str = Field("Untitled profile", min_length=1, max_length=200)
    content: CvContent | None = None
    """Starter sections when omitted."""


class ProfileUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    content: CvContent | None = None
    is_default: Literal[True] | None = None
    """Make this the default profile (the previous default stops being one)."""


@router.get("")
async def list_profiles(profiles: Profiles) -> list[ProfileSummary]:
    rows = await service.list_profiles(profiles)
    return [ProfileSummary.model_validate(row) for row in rows]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_profile(body: ProfileCreate, profiles: Profiles) -> Profile:
    row = await service.create_profile(profiles, body.name, body.content)
    return Profile.model_validate(row)


@router.get("/{profile_id}")
async def get_profile(profile_id: uuid.UUID, profiles: Profiles) -> Profile:
    return Profile.model_validate(await service.get_profile(profiles, profile_id))


@router.patch("/{profile_id}")
async def update_profile(profile_id: uuid.UUID, body: ProfileUpdate, profiles: Profiles) -> Profile:
    row = await service.update_profile(
        profiles,
        profile_id,
        name=body.name,
        content=body.content,
        make_default=bool(body.is_default),
    )
    return Profile.model_validate(row)


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile(profile_id: uuid.UUID, profiles: Profiles) -> None:
    await service.delete_profile(profiles, profile_id)


@router.post("/{profile_id}/duplicate", status_code=status.HTTP_201_CREATED)
async def duplicate_profile(profile_id: uuid.UUID, profiles: Profiles) -> Profile:
    return Profile.model_validate(await service.duplicate_profile(profiles, profile_id))
