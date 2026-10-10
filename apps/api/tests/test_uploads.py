"""Uploads service: type and size checks, storage keys, and per-user scoping."""

import io
import zipfile
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from api.errors import NotFound, ValidationFailed
from api.ports.auth import Identity
from api.ports.storage import LocalStorage
from api.repositories.uploads import UploadRepository
from api.repositories.users import UserRepository
from api.services import uploads as service
from api.services.users import ensure_user

PDF_BYTES = b"%PDF-1.7\n1 0 obj\n"


def zip_with(*names: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name in names:
            archive.writestr(name, "<xml/>")
    return buffer.getvalue()


DOCX_BYTES = zip_with("[Content_Types].xml", "word/document.xml")


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (PDF_BYTES, service.PDF),
        (DOCX_BYTES, service.DOCX),
        (zip_with("xl/workbook.xml"), None),
        (b"PK\x03\x04 not really a zip", None),
        (b"plain text", None),
        (b"", None),
    ],
)
def test_detect_mime_type(data: bytes, expected: str | None) -> None:
    assert service.detect_mime_type(data) == expected


async def repo_for(session: AsyncSession, email: str) -> UploadRepository:
    user = await ensure_user(UserRepository(session), Identity(uid=f"uid:{email}", email=email))
    return UploadRepository(session, user.id)


async def test_store_read_list_and_delete(db_session: AsyncSession, tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    uploads = await repo_for(db_session, "ada@example.com")

    upload = await service.store_upload(uploads, storage, "C:\\Users\\ada\\My CV.pdf", PDF_BYTES)

    assert upload.filename == "My CV.pdf"
    assert upload.mime_type == service.PDF
    assert upload.size_bytes == len(PDF_BYTES)
    assert upload.storage_key == f"uploads/{uploads.user_id}/{upload.id}"
    assert await service.read_upload(uploads, storage, upload.id) == PDF_BYTES
    assert [u.id for u in await service.list_uploads(uploads)] == [upload.id]

    await service.delete_upload(uploads, storage, upload.id)

    assert await service.list_uploads(uploads) == []
    with pytest.raises(NotFound):
        await storage.get(upload.storage_key)


async def test_docx_is_accepted(db_session: AsyncSession, tmp_path: Path) -> None:
    uploads = await repo_for(db_session, "ada@example.com")

    upload = await service.store_upload(uploads, LocalStorage(tmp_path), "cv.docx", DOCX_BYTES)

    assert upload.mime_type == service.DOCX


async def test_other_files_are_refused(db_session: AsyncSession, tmp_path: Path) -> None:
    uploads = await repo_for(db_session, "ada@example.com")

    with pytest.raises(ValidationFailed, match="not a PDF or DOCX"):
        await service.store_upload(uploads, LocalStorage(tmp_path), "cv.pdf", b"<html>")


async def test_large_files_are_refused(db_session: AsyncSession, tmp_path: Path) -> None:
    uploads = await repo_for(db_session, "ada@example.com")
    data = PDF_BYTES + b"0" * service.MAX_UPLOAD_BYTES

    with pytest.raises(ValidationFailed, match="larger than 10 MB"):
        await service.store_upload(uploads, LocalStorage(tmp_path), "cv.pdf", data)


async def test_blank_filenames_get_a_name(db_session: AsyncSession, tmp_path: Path) -> None:
    uploads = await repo_for(db_session, "ada@example.com")

    upload = await service.store_upload(uploads, LocalStorage(tmp_path), "  ", PDF_BYTES)

    assert upload.filename == "upload"


async def test_users_cannot_reach_each_others_uploads(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    storage = LocalStorage(tmp_path)
    ada = await repo_for(db_session, "ada@example.com")
    bob = await repo_for(db_session, "bob@example.com")
    upload = await service.store_upload(ada, storage, "cv.pdf", PDF_BYTES)

    assert await service.list_uploads(bob) == []
    with pytest.raises(NotFound):
        await service.read_upload(bob, storage, upload.id)
    with pytest.raises(NotFound):
        await service.delete_upload(bob, storage, upload.id)
    assert await service.read_upload(ada, storage, upload.id) == PDF_BYTES
