import uuid
from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile
from pydantic import BaseModel

from api.ai.models import AiModel
from api.deps import AiRuns, AppSettings, CurrentUser, FileStorage, Providers, Uploads
from api.errors import AI_ERROR_RESPONSES
from api.ports.llm.base import ProviderName
from api.services import imports as service
from api.services.ai_models import choose_model
from api.services.uploads import MAX_UPLOAD_BYTES
from cvcore.models import CvContent

router = APIRouter(prefix="/imports", tags=["imports"], responses=AI_ERROR_RESPONSES)


class ImportResult(BaseModel):
    upload_id: uuid.UUID | None
    """The stored file, for importing again later; None for pasted text."""
    draft: CvContent
    """Not saved: the SPA saves it with POST /profiles after review."""
    ai_model: AiModel
    provider: ProviderName
    model: str
    """The provider's model id that answered."""


@router.post("")
async def create_import(
    user: CurrentUser,
    providers: Providers,
    settings: AppSettings,
    runs: AiRuns,
    uploads: Uploads,
    storage: FileStorage,
    file: Annotated[UploadFile | None, File(description="A PDF or DOCX, up to 10 MB")] = None,
    text: Annotated[str | None, Form(description="The CV pasted as text")] = None,
    upload_id: Annotated[uuid.UUID | None, Form(description="Import an earlier upload")] = None,
    ai_model: Annotated[AiModel | None, Form(description="Default: the user's choice")] = None,
) -> ImportResult:
    """Extract a profile draft with the chosen AI model (default: the user's choice)."""
    upload = None
    if file is not None:
        # One byte over the limit is enough for the size check.
        upload = (file.filename or "upload", await file.read(MAX_UPLOAD_BYTES + 1))
    choice = choose_model(
        providers,
        user,
        ai_model,
        default=settings.default_ai_model,
        enforce_plans=settings.enforce_ai_plans,
    )
    result = await service.import_profile(
        choice,
        runs,
        uploads,
        storage,
        file=upload,
        text=text,
        upload_id=upload_id,
    )
    return ImportResult(
        upload_id=result.upload_id,
        draft=result.draft,
        ai_model=result.choice.option.id,
        provider=result.choice.option.provider,
        model=result.model,
    )
