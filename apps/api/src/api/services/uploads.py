"""Uploaded files: PDF or DOCX up to 10 MB, stored under uploads/<user_id>/ with a row each."""

import io
import uuid
import zipfile
from collections.abc import Sequence

from api.db.models import Upload
from api.errors import NotFound, ValidationFailed
from api.ports.storage import Storage
from api.repositories.uploads import UploadRepository

MAX_UPLOAD_BYTES = 10 * 1024 * 1024

PDF = "application/pdf"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def detect_mime_type(data: bytes) -> str | None:
    """PDF or DOCX by content, never by file name or the browser's claim."""
    if data.startswith(b"%PDF-"):
        return PDF
    if data.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                if "word/document.xml" in archive.namelist():
                    return DOCX
        except zipfile.BadZipFile:
            return None
    return None


def user_prefix(user_id: uuid.UUID) -> str:
    return f"uploads/{user_id}"


def storage_key(user_id: uuid.UUID, upload_id: uuid.UUID) -> str:
    return f"{user_prefix(user_id)}/{upload_id}"


def _clean_filename(filename: str) -> str:
    name = filename.replace("\\", "/").rsplit("/", 1)[-1].strip()
    return name[:255] or "upload"


async def store_upload(
    uploads: UploadRepository, storage: Storage, filename: str, data: bytes
) -> Upload:
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValidationFailed("This file is larger than 10 MB. Upload a smaller file.")
    mime_type = detect_mime_type(data)
    if mime_type is None:
        raise ValidationFailed("This file is not a PDF or DOCX. Upload a PDF or DOCX file.")
    upload_id = uuid.uuid4()
    key = storage_key(uploads.user_id, upload_id)
    await storage.put(key, data, mime_type)
    return await uploads.create(
        id=upload_id,
        storage_key=key,
        filename=_clean_filename(filename),
        mime_type=mime_type,
        size_bytes=len(data),
    )


async def list_uploads(uploads: UploadRepository) -> Sequence[Upload]:
    return await uploads.list_recent()


async def get_upload(uploads: UploadRepository, upload_id: uuid.UUID) -> Upload:
    upload = await uploads.get(upload_id)
    if upload is None:
        raise NotFound("This file does not exist or was deleted.")
    return upload


async def read_upload(uploads: UploadRepository, storage: Storage, upload_id: uuid.UUID) -> bytes:
    return await storage.get((await get_upload(uploads, upload_id)).storage_key)


async def delete_upload(uploads: UploadRepository, storage: Storage, upload_id: uuid.UUID) -> None:
    upload = await get_upload(uploads, upload_id)
    await uploads.delete(upload.id)
    await storage.delete(upload.storage_key)
