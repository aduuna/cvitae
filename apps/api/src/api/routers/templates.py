from fastapi import APIRouter

from api.deps import AppSettings, CurrentUser, Profiles, Renderer
from api.errors import ERROR_RESPONSES
from api.services.templates import list_templates, preview_template
from cvcore.rendering import Paper, SvgPages, TemplateMeta

router = APIRouter(prefix="/templates", tags=["templates"], responses=ERROR_RESPONSES)


@router.get("")
async def get_templates(_: CurrentUser, renderer: Renderer) -> list[TemplateMeta]:
    return await list_templates(renderer)


@router.get("/{template_id}/preview")
async def get_template_preview(
    template_id: str,
    profiles: Profiles,
    renderer: Renderer,
    settings: AppSettings,
    paper: Paper = "a4",
) -> SvgPages:
    """The template rendered with the user's default profile, or sample data."""
    return await preview_template(
        profiles, renderer, template_id, sample_path=settings.sample_profile_path, paper=paper
    )
