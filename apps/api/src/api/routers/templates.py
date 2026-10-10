from fastapi import APIRouter

from api.deps import CurrentUser, Renderer
from api.errors import ERROR_RESPONSES
from api.services.templates import list_templates
from cvcore.rendering import TemplateMeta

router = APIRouter(prefix="/templates", tags=["templates"], responses=ERROR_RESPONSES)


@router.get("")
async def get_templates(_: CurrentUser, renderer: Renderer) -> list[TemplateMeta]:
    return await list_templates(renderer)
