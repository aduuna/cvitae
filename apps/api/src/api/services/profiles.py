"""Profiles: a user's master career data. One profile per user is the default."""

import uuid
from collections.abc import Sequence

from api.db.models import Profile
from api.errors import NotFound
from api.repositories.profiles import ProfileRepository
from cvcore.ids import new_id
from cvcore.models import Basics, CvContent, Section, SectionKind

STARTER_SECTIONS: list[tuple[SectionKind, str]] = [
    ("experience", "Experience"),
    ("education", "Education"),
    ("skills", "Skills"),
]


def starter_content() -> CvContent:
    """What a new profile starts with: empty basics and the three most common sections."""
    return CvContent(
        basics=Basics(name=""),
        sections=[Section(id=new_id(), kind=kind, title=title) for kind, title in STARTER_SECTIONS],
    )


async def list_profiles(profiles: ProfileRepository) -> Sequence[Profile]:
    return await profiles.list_recent()


async def get_profile(profiles: ProfileRepository, profile_id: uuid.UUID) -> Profile:
    profile = await profiles.get(profile_id)
    if profile is None:
        raise NotFound("This profile does not exist or was deleted.")
    return profile


async def create_profile(
    profiles: ProfileRepository, name: str, content: CvContent | None = None
) -> Profile:
    first = await profiles.count() == 0
    return await profiles.create(
        name=name,
        is_default=first,
        content=(content or starter_content()).model_dump(mode="json"),
    )


async def update_profile(
    profiles: ProfileRepository,
    profile_id: uuid.UUID,
    *,
    name: str | None = None,
    content: CvContent | None = None,
    make_default: bool = False,
) -> Profile:
    profile = await get_profile(profiles, profile_id)
    values: dict[str, object] = {}
    if name is not None:
        values["name"] = name
    if content is not None:
        values["content"] = content.model_dump(mode="json")
    if make_default and not profile.is_default:
        await profiles.clear_default()
        values["is_default"] = True
    return await profiles.update(profile, **values)


async def duplicate_profile(profiles: ProfileRepository, profile_id: uuid.UUID) -> Profile:
    source = await get_profile(profiles, profile_id)
    return await profiles.create(
        name=f"{source.name} (copy)", is_default=False, content=dict(source.content)
    )


async def delete_profile(profiles: ProfileRepository, profile_id: uuid.UUID) -> None:
    profile = await get_profile(profiles, profile_id)
    was_default = profile.is_default
    await profiles.delete(profile.id)
    if was_default:
        remaining = await profiles.list_recent()
        if remaining:
            await profiles.update(remaining[0], is_default=True)
