from api.errors import ValidationFailed
from api.ports.renderer import RendererClient
from cvcore.rendering import TemplateMeta

DEFAULT_TEMPLATE_ID = "classic"


async def list_templates(renderer: RendererClient) -> list[TemplateMeta]:
    return await renderer.templates()


async def require_template(renderer: RendererClient, template_id: str) -> TemplateMeta:
    for template in await renderer.templates():
        if template.id == template_id:
            return template
    raise ValidationFailed(f"There is no template called {template_id}.", {"field": "template_id"})
