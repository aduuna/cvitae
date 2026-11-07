import asyncio
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Annotated, Literal

from fastapi import APIRouter, File, Form, UploadFile, status
from pydantic import BaseModel, Field

from api.ai.models import AiModel
from api.deps import (
    AiRuns,
    AppSettings,
    Catalog,
    CurrentUser,
    Documents,
    FileStorage,
    Profiles,
    Providers,
    Renderer,
    Uploads,
    UserPlan,
    Users,
    UserTemplates,
)
from api.errors import AI_ERROR_RESPONSES, ERROR_RESPONSES, ErrorEnvelope
from api.ports.llm.base import ProviderName
from api.services import user_templates as custom
from api.services.ai_models import choose_claude_model
from api.services.templates import preview_template
from api.services.uploads import MAX_UPLOAD_BYTES
from cvcore.rendering import Paper, SvgPages, TemplateMeta, TemplateSource

if TYPE_CHECKING:
    from api.db.models import UserTemplate

router = APIRouter(prefix="/templates", tags=["templates"], responses=ERROR_RESPONSES)


class CustomTemplate(BaseModel):
    """A template the user made from their own CV."""

    id: str
    """The template id: use it as `template_id` like a built-in one, once it is ready."""
    name: str
    description: str
    status: Literal["draft", "ready"]
    """A draft can be previewed and read but not used; confirm it with PATCH."""
    paper_sizes: list[Paper]
    target_pages: int
    upload_id: uuid.UUID | None
    """The PDF it was made from; None after that upload is deleted."""
    created_at: datetime
    updated_at: datetime


def to_custom(row: "UserTemplate") -> CustomTemplate:
    return CustomTemplate.model_validate(
        {
            "id": row.slug,
            "name": row.name,
            "description": row.description,
            "status": row.status,
            "paper_sizes": row.paper_sizes,
            "target_pages": row.target_pages,
            "upload_id": row.upload_id,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
    )


class CustomTemplateDraft(CustomTemplate):
    """What generating a template returns: the new draft, and what ran."""

    ai_model: AiModel
    provider: ProviderName
    model: str
    """The provider's model id that answered."""


class CustomTemplateUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=60)
    description: str | None = Field(None, max_length=200)
    status: Literal["ready"] | None = None
    """"ready" confirms a draft, which needs room under the plan's limit."""


@router.get("")
async def get_templates(_: CurrentUser, catalog: Catalog) -> list[TemplateMeta]:
    """The built-in templates, then the user's own ready ones (`custom` is true for those)."""
    return await catalog.available()


@router.post(
    "/custom",
    status_code=status.HTTP_201_CREATED,
    responses={
        **AI_ERROR_RESPONSES,
        503: {"model": ErrorEnvelope, "description": "The server has no Claude key"},
    },
)
async def create_custom_template(
    user: CurrentUser,
    plan: UserPlan,
    providers: Providers,
    settings: AppSettings,
    runs: AiRuns,
    uploads: Uploads,
    storage: FileStorage,
    templates: UserTemplates,
    renderer: Renderer,
    file: Annotated[UploadFile | None, File(description="A PDF, up to 10 MB")] = None,
    upload_id: Annotated[uuid.UUID | None, Form(description="Use an earlier upload")] = None,
) -> CustomTemplateDraft:
    """Draft a template in the design of a CV, with Claude. Takes one AI run and up to about two
    minutes; the request waits. The result is a draft: preview it, then confirm it with PATCH.
    Send a PDF as `file`, or the `upload_id` of one uploaded before (a DOCX is refused)."""
    choice = choose_claude_model(
        providers, user, enforce_plans=settings.enforce_ai_plans, plan=plan
    )
    sent = None
    if file is not None:
        # One byte over the limit is enough for the size check.
        sent = (file.filename or "upload", await file.read(MAX_UPLOAD_BYTES + 1))
    kit = await asyncio.to_thread(custom.load_kit, settings.templates_dir)
    result = await custom.generate_template(
        choice,
        runs,
        uploads,
        storage,
        templates,
        renderer,
        plan=plan,
        kit=kit,
        file=sent,
        upload_id=upload_id,
    )
    return CustomTemplateDraft(
        **to_custom(result.template).model_dump(),
        ai_model=result.choice.option.id,
        provider=result.choice.option.provider,
        model=result.model,
    )


@router.patch("/custom/{template_id}", responses={402: {"model": ErrorEnvelope}})
async def update_custom_template(
    template_id: str, body: CustomTemplateUpdate, plan: UserPlan, templates: UserTemplates
) -> CustomTemplate:
    """Rename or describe a template, or confirm a draft (`status: "ready"`)."""
    row = await custom.update_custom(
        templates,
        template_id,
        plan=plan,
        name=body.name,
        description=body.description,
        confirm=body.status == "ready",
    )
    return to_custom(row)


@router.delete("/custom/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_custom_template(
    template_id: str,
    user: CurrentUser,
    users: Users,
    documents: Documents,
    templates: UserTemplates,
    catalog: Catalog,
) -> None:
    """Delete a template. CVs that use it switch to the user's default template (Classic when
    the default was this one), and the default resets to Classic."""
    await custom.delete_custom(templates, documents, users, catalog, user, template_id)


@router.get("/{template_id}/preview")
async def get_template_preview(
    template_id: str,
    profiles: Profiles,
    catalog: Catalog,
    settings: AppSettings,
    paper: Paper = "a4",
) -> SvgPages:
    """The template rendered with the user's default profile, or sample data. Works for the
    user's own templates, drafts included."""
    return await preview_template(
        profiles, catalog, template_id, sample_path=settings.sample_profile_path, paper=paper
    )


@router.get("/{template_id}/source")
async def get_template_source(template_id: str, catalog: Catalog) -> TemplateSource:
    """The main.typ of a built-in template or one of the user's own, where a CV's custom layout
    starts. Another user's template is a 404."""
    return await catalog.source(template_id)
