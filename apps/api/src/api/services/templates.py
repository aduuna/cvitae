import asyncio
from pathlib import Path

from api.errors import ValidationFailed
from api.ports.renderer import RendererClient
from api.repositories.profiles import ProfileRepository
from cvcore.models import CvContent
from cvcore.render import to_render_json
from cvcore.rendering import Paper, SvgPages, TemplateMeta

DEFAULT_TEMPLATE_ID = "classic"


async def list_templates(renderer: RendererClient) -> list[TemplateMeta]:
    return await renderer.templates()


async def require_template(renderer: RendererClient, template_id: str) -> TemplateMeta:
    for template in await renderer.templates():
        if template.id == template_id:
            return template
    raise ValidationFailed(f"There is no template called {template_id}.", {"field": "template_id"})


async def preview_template(
    profiles: ProfileRepository,
    renderer: RendererClient,
    template_id: str,
    *,
    sample_path: Path,
    paper: Paper = "a4",
) -> SvgPages:
    """The template rendered with the user's default profile, or the sample profile when they
    have none (or it has no name yet)."""
    template = await require_template(renderer, template_id)
    default = await profiles.get_default()
    content = CvContent.model_validate(default.content) if default else None
    if content is None or not content.basics.name.strip():
        content = CvContent.model_validate_json(await asyncio.to_thread(sample_path.read_text))
    return await renderer.render_svg(template.id, to_render_json(content), paper)
