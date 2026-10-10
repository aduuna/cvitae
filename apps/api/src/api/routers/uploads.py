import uuid
from datetime import datetime

from fastapi import APIRouter, status
from pydantic import BaseModel, ConfigDict

from api.deps import FileStorage, Uploads
from api.errors import ERROR_RESPONSES
from api.services import uploads as service

router = APIRouter(prefix="/uploads", tags=["uploads"], responses=ERROR_RESPONSES)


class UploadSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    mime_type: str
    size_bytes: int
    created_at: datetime


@router.get("")
async def list_uploads(uploads: Uploads) -> list[UploadSummary]:
    return [UploadSummary.model_validate(row) for row in await service.list_uploads(uploads)]


@router.delete("/{upload_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_upload(upload_id: uuid.UUID, uploads: Uploads, storage: FileStorage) -> None:
    await service.delete_upload(uploads, storage, upload_id)
