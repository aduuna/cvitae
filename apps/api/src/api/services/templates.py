"""The templates a user can use: the built-in ones the renderer holds, and their own, made from
their CVs (docs/BACKEND.md, Custom templates). Every place that names or renders a template goes
through the catalog, so a custom id resolves the same way everywhere and only for its owner."""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from api.db.models import UserTemplate
from api.errors import NotFound, ValidationFailed
from api.ports.renderer import RendererClient
from api.repositories.profiles import ProfileRepository
from api.repositories.user_templates import UserTemplateRepository
from cvcore.models import CvContent
from cvcore.render import to_render_json
from cvcore.rendering import Paper, SvgPages, TemplateMeta
from cvcore.user_templates import is_custom_id

DEFAULT_TEMPLATE_ID = "classic"

CUSTOM_PAPER_SIZES: list[Paper] = ["a4", "us-letter"]
"""Every custom template sizes its page with `paper-size()`, so it fits both."""


@dataclass(frozen=True)
class Template:
    meta: TemplateMeta
    source: str | None
    """The main.typ of a user's own template, which the renderer is sent; None for a built-in
    one, which the renderer already holds."""


def custom_meta(row: UserTemplate) -> TemplateMeta:
    return TemplateMeta(
        id=row.slug,
        name=row.name,
        description=row.description,
        paper_sizes=[size for size in CUSTOM_PAPER_SIZES if size in row.paper_sizes],
        target_pages=row.target_pages,
        custom=True,
    )


class TemplateCatalog:
    """The renderer's templates and one user's own. Built for a user, so another user's template
    is never found."""

    def __init__(self, renderer: RendererClient, user_templates: UserTemplateRepository) -> None:
        self.renderer = renderer
        self.user_templates = user_templates

    async def available(self) -> list[TemplateMeta]:
        """The built-in templates, then the user's own in the order they were made. A draft is
        not there until the user confirms it."""
        built_in = await self.renderer.templates()
        return [*built_in, *(custom_meta(row) for row in await self.user_templates.list_ready())]

    async def get(self, template_id: str, *, drafts: bool = False) -> Template:
        """A template by id. `drafts`: also find the user's unconfirmed generation, which can be
        previewed but not used. A custom id that is not the user's (or was deleted) is a 404, so
        ids tell nothing about other users; an unknown built-in id is a 422, as it always was."""
        if is_custom_id(template_id):
            row = await self.user_templates.get_by_slug(template_id)
            if row is None or (row.status != "ready" and not drafts):
                raise NotFound("This template does not exist or was deleted.")
            return Template(meta=custom_meta(row), source=row.main_typ)
        for template in await self.renderer.templates():
            if template.id == template_id:
                return Template(meta=template, source=None)
        raise ValidationFailed(
            f"There is no template called {template_id}.", {"field": "template_id"}
        )

    async def require(self, template_id: str) -> TemplateMeta:
        """The template's metadata, for a CV or default that is about to use it."""
        return (await self.get(template_id)).meta

    async def render_svg(
        self,
        template_id: str,
        data: dict[str, Any],
        paper: Paper,
        *,
        source_links: bool = False,
    ) -> SvgPages:
        template = await self.get(template_id)
        return await self.renderer.render_svg(
            template.meta.id, data, paper, source_links=source_links, source=template.source
        )

    async def render_pdf(self, template_id: str, data: dict[str, Any], paper: Paper) -> bytes:
        template = await self.get(template_id)
        return await self.renderer.render_pdf(template.meta.id, data, paper, source=template.source)


async def preview_template(
    profiles: ProfileRepository,
    catalog: TemplateCatalog,
    template_id: str,
    *,
    sample_path: Path,
    paper: Paper = "a4",
) -> SvgPages:
    """The template rendered with the user's default profile, or the sample profile when they
    have none (or it has no name yet). A custom template's draft can be previewed before it is
    confirmed."""
    template = await catalog.get(template_id, drafts=True)
    default = await profiles.get_default()
    content = CvContent.model_validate(default.content) if default else None
    if content is None or not content.basics.name.strip():
        content = CvContent.model_validate_json(await asyncio.to_thread(sample_path.read_text))
    return await catalog.renderer.render_svg(
        template.meta.id, to_render_json(content), paper, source=template.source
    )
