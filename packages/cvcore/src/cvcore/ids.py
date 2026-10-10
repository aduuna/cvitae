"""Ids for items inside CV content (bullets, entries, sections)."""

import secrets
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cvcore.models import Bullet, CvContent


def new_id() -> str:
    """A random 12-character hex id. The frontend generates ids in the same format."""
    return secrets.token_hex(6)


def with_fresh_ids(content: "CvContent") -> "CvContent":
    """A copy with a new id on every section, entry, skill group and bullet, and no source ids.
    For drafts a model produced: their ids are not trusted to be unique."""
    fresh = content.model_copy(deep=True)
    for section in fresh.sections:
        section.id = new_id()
        items = [
            *section.experience,
            *section.projects,
            *section.education,
            *section.skills,
            *section.certifications,
        ]
        for item in items:
            item.id = new_id()
        for experience in section.experience:
            for engagement in experience.engagements:
                engagement.id = new_id()
                _fresh_bullets(engagement.bullets)
            _fresh_bullets(experience.bullets)
        for project in section.projects:
            _fresh_bullets(project.bullets)
        _fresh_bullets(section.custom)
    return fresh


def _fresh_bullets(bullets: "list[Bullet]") -> None:
    for bullet in bullets:
        bullet.id = new_id()
        bullet.source_id = None
