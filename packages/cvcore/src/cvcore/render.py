"""Turn CV content into the renderer's data.json, and find the placeholders a CV still has."""

from collections.abc import Iterator
from typing import Any

from pydantic import BaseModel

from cvcore.models import Bullet, CvContent
from cvcore.richtext import parse


class PlaceholderRef(BaseModel):
    text: str
    bullet_id: str | None = None
    """The bullet holding the placeholder; None means the summary."""


def to_render_json(content: CvContent) -> dict[str, Any]:
    """data.json for a template: every bullet and the summary become spans, so Typst never
    evaluates user text as markup. Bullets keep their `id` (previews link to it) and lose
    `source_id`."""
    data = content.model_dump(mode="json")
    data["summary"] = _spans(content.summary)
    for section in data["sections"]:
        section["custom"] = _bullets(section["custom"])
        for item in section["experience"]:
            item["bullets"] = _bullets(item["bullets"])
            for engagement in item["engagements"]:
                engagement["bullets"] = _bullets(engagement["bullets"])
        for item in section["projects"]:
            item["bullets"] = _bullets(item["bullets"])
    return data


def _spans(text: str) -> list[dict[str, Any]]:
    return [span.model_dump() for span in parse(text)]


def _bullets(bullets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"id": bullet["id"], "spans": _spans(bullet["text"])} for bullet in bullets]


def iter_bullets(content: CvContent) -> Iterator[Bullet]:
    """Every bullet in reading order."""
    for section in content.sections:
        for item in section.experience:
            yield from item.bullets
            for engagement in item.engagements:
                yield from engagement.bullets
        for project in section.projects:
            yield from project.bullets
        yield from section.custom


def find_placeholders(content: CvContent) -> list[PlaceholderRef]:
    """Placeholders left in the summary and bullets, in reading order."""
    refs = [PlaceholderRef(text=span.t) for span in parse(content.summary) if span.p]
    for bullet in iter_bullets(content):
        refs.extend(
            PlaceholderRef(text=span.t, bullet_id=bullet.id)
            for span in parse(bullet.text)
            if span.p
        )
    return refs
