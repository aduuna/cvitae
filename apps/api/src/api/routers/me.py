import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Response, status
from pydantic import BaseModel, ConfigDict, Field

from api.ai.models import AiModel
from api.billing.plans import Plan
from api.db.base import utcnow
from api.db.models import Document, DocumentVersion
from api.deps import (
    AccountRepos,
    Catalog,
    CurrentUser,
    FileStorage,
    Providers,
    Subscriptions,
    UserPlan,
    Users,
)
from api.errors import ERROR_RESPONSES, ErrorEnvelope
from api.services import account
from api.services import users as service

router = APIRouter(prefix="/me", tags=["me"], responses=ERROR_RESPONSES)


class Me(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str | None
    preferred_ai_model: AiModel | None
    """The model the user chose, if it is still offered; None means the server's default."""
    plan: Plan
    """The plan the user is on now."""
    default_template_id: str | None


class MeUpdate(BaseModel):
    display_name: str | None = Field(None, max_length=200)
    preferred_ai_model: AiModel | None = None
    default_template_id: str | None = Field(None, min_length=1, max_length=64)


def me(user: object, plan: Plan, providers: Providers) -> Me:
    result = Me.model_validate(user)
    result.plan = plan
    if result.preferred_ai_model and not providers.option(result.preferred_ai_model):
        result.preferred_ai_model = None
    return result


@router.get("")
async def get_me(user: CurrentUser, plan: UserPlan, providers: Providers) -> Me:
    return me(user, plan, providers)


@router.patch("")
async def update_me(
    body: MeUpdate,
    user: CurrentUser,
    plan: UserPlan,
    users: Users,
    catalog: Catalog,
    providers: Providers,
) -> Me:
    row = await service.update_me(
        users,
        catalog,
        providers,
        user,
        display_name=body.display_name,
        preferred_ai_model=body.preferred_ai_model,
        default_template_id=body.default_template_id,
    )
    return me(row, plan, providers)


class ExportRow(BaseModel):
    """Rows of the export are read as they are stored."""

    model_config = ConfigDict(from_attributes=True)


class ExportAccount(ExportRow):
    id: uuid.UUID
    email: str
    display_name: str | None
    preferred_ai_model: str | None
    plan: Plan
    default_template_id: str | None
    created_at: datetime


class ExportProfile(ExportRow):
    id: uuid.UUID
    name: str
    is_default: bool
    content: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ExportJob(ExportRow):
    id: uuid.UUID
    title: str
    company: str
    url: str | None
    description: str
    analysis: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


class ExportVersion(ExportRow):
    number: int
    reason: Literal["tailor", "manual", "restore", "autosave"]
    content: dict[str, Any]
    source_files: dict[str, str] | None
    created_at: datetime


class ExportDocument(ExportRow):
    id: uuid.UUID
    name: str
    template_id: str
    mode: Literal["structured", "ejected"]
    profile_id: uuid.UUID | None
    job_id: uuid.UUID | None
    page_count: int | None
    content: dict[str, Any]
    source_files: dict[str, str] | None
    """`main.typ` and `data.json` of an ejected CV."""
    versions: list[ExportVersion] = []
    """Oldest first."""
    created_at: datetime
    updated_at: datetime


class ExportTemplate(ExportRow):
    id: str = Field(validation_alias="slug")
    """The template id, which the database keeps in `slug`."""
    name: str
    description: str
    status: Literal["draft", "ready"]
    main_typ: str
    paper_sizes: list[str]
    target_pages: int
    created_at: datetime
    updated_at: datetime


class ExportUpload(ExportRow):
    """What is known about a file the user uploaded. The file itself is not in the export: it is
    the user's own, and an upload can be 10 MB."""

    id: uuid.UUID
    filename: str
    mime_type: str
    size_bytes: int
    created_at: datetime


class ExportAiRun(ExportRow):
    """One AI call. There is no prompt or output: none is kept."""

    id: uuid.UUID
    task: str
    provider: str
    model: str
    status: str
    error_code: str | None
    input_tokens: int
    output_tokens: int
    cost_usd: float | None
    duration_ms: int
    created_at: datetime


class ExportSubscription(ExportRow):
    plan_code: str
    status: str
    current_period_end: datetime | None
    paystack_customer_code: str
    paystack_subscription_code: str | None
    created_at: datetime


class ExportConnection(ExportRow):
    """A browser the extension is connected in. Only a hash of its token is kept, so it is not
    here."""

    id: uuid.UUID
    label: str
    created_at: datetime
    last_used_at: datetime | None


class AccountExport(BaseModel):
    """Everything the account holds, as JSON."""

    exported_at: datetime
    account: ExportAccount
    profiles: list[ExportProfile]
    jobs: list[ExportJob]
    documents: list[ExportDocument]
    templates: list[ExportTemplate]
    uploads: list[ExportUpload]
    ai_runs: list[ExportAiRun]
    subscription: ExportSubscription | None
    extension_connections: list[ExportConnection]


EXPORT_FILENAME = "chameleon-vitae-export.json"


def export_document(row: Document, versions: Sequence[DocumentVersion]) -> ExportDocument:
    document = ExportDocument.model_validate(row)
    document.versions = [ExportVersion.model_validate(version) for version in versions]
    return document


def to_export(data: account.AccountData, exported_at: datetime) -> AccountExport:
    return AccountExport(
        exported_at=exported_at,
        account=ExportAccount.model_validate(data.user),
        profiles=[ExportProfile.model_validate(row) for row in data.profiles],
        jobs=[ExportJob.model_validate(row) for row in data.jobs],
        documents=[export_document(row, data.versions.get(row.id, ())) for row in data.documents],
        templates=[ExportTemplate.model_validate(row) for row in data.templates],
        uploads=[ExportUpload.model_validate(row) for row in data.uploads],
        ai_runs=[ExportAiRun.model_validate(row) for row in data.ai_runs],
        subscription=(
            ExportSubscription.model_validate(data.subscription) if data.subscription else None
        ),
        extension_connections=[ExportConnection.model_validate(row) for row in data.connections],
    )


@router.get("/export")
async def export_me(
    user: CurrentUser, repositories: AccountRepos, response: Response
) -> AccountExport:
    """All of the user's data as one JSON file."""
    data = await account.export_account(user, repositories)
    response.headers["Content-Disposition"] = f'attachment; filename="{EXPORT_FILENAME}"'
    return to_export(data, utcnow())


class AccountDelete(BaseModel):
    email: str = Field(max_length=320)
    """The account's email address, typed to confirm."""


@router.delete(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={409: {"model": ErrorEnvelope, "description": "A Pro subscription is still active"}},
)
async def delete_me(
    body: AccountDelete,
    user: CurrentUser,
    users: Users,
    subscriptions: Subscriptions,
    storage: FileStorage,
) -> None:
    """Delete the account and everything in it: rows and stored files."""
    await account.delete_account(users, subscriptions, storage, user, body.email)
