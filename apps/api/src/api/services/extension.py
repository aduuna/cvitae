"""The browser extension: connecting it to an account, and what it may read and save.

The extension holds a token instead of a Firebase session. The token works on the extension's own
routes only: it can read profiles and CVs, export a CV as PDF and save jobs, nothing else. Only its
SHA-256 is stored, and the user can disconnect any browser from Settings."""

import hashlib
import secrets
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from api.db.models import Document, ExtensionToken, Job, Profile, User
from api.errors import NotFound, Unauthorized
from api.ports.renderer import RendererClient
from api.repositories.documents import DocumentRepository
from api.repositories.extension_tokens import ExtensionTokenLookup, ExtensionTokenRepository
from api.repositories.jobs import JobRepository
from api.repositories.profiles import ProfileRepository
from api.services import jobs as job_service
from api.services import rendering
from api.services.documents import get_document
from api.services.profiles import get_profile
from cvcore.application import ApplicationData, to_application_data
from cvcore.models import CvContent
from cvcore.render import find_placeholders

TOKEN_PREFIX = "cvx_"  # noqa: S105 - marks the token type; not a secret
MAX_CONNECTIONS = 10
"""Connecting an eleventh browser disconnects the one used least recently."""
TOUCH_EVERY = timedelta(hours=1)
"""How often `last_used_at` is written: often enough for Settings, without a write per request."""


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def connect(tokens: ExtensionTokenRepository, label: str) -> tuple[ExtensionToken, str]:
    """A new connection and its token. The token is returned this once and never stored."""
    while await tokens.count() >= MAX_CONNECTIONS:
        oldest = await tokens.least_recently_used()
        if oldest is None:  # pragma: no cover - count() said there is one
            break
        await tokens.delete(oldest.id)
    token = TOKEN_PREFIX + secrets.token_urlsafe(32)
    row = await tokens.create(
        label=label.strip()[:100] or "Browser extension", token_hash=hash_token(token)
    )
    return row, token


async def list_connections(tokens: ExtensionTokenRepository) -> Sequence[ExtensionToken]:
    return await tokens.list_recent()


async def disconnect(tokens: ExtensionTokenRepository, token_id: uuid.UUID) -> None:
    if not await tokens.delete(token_id):
        raise NotFound("This browser is not connected.")


@dataclass(frozen=True)
class Connection:
    token: ExtensionToken
    user: User


async def authenticate(
    lookup: ExtensionTokenLookup, token: str | None, now: datetime
) -> Connection:
    if not token or not token.startswith(TOKEN_PREFIX):
        raise Unauthorized("Connect the extension to your account first.")
    found = await lookup.owner(hash_token(token))
    if found is None:
        raise Unauthorized("This browser is no longer connected. Connect the extension again.")
    row, user = found
    if row.last_used_at is None or now - row.last_used_at >= TOUCH_EVERY:
        await lookup.touch(row.id, now)
    return Connection(token=row, user=user)


@dataclass(frozen=True)
class CvSource:
    document: Document
    placeholders: int


@dataclass(frozen=True)
class Sources:
    profiles: Sequence[Profile]
    documents: list[CvSource]
    jobs: Sequence[Job]


async def list_sources(
    profiles: ProfileRepository, documents: DocumentRepository, jobs: JobRepository
) -> Sources:
    """What a form can be filled from: profiles and CVs, newest first, and the saved jobs so the
    extension can tell which CV was made for the page it is on. Ejected CVs are left out: their
    Typst source, not their content, is what the user edits."""
    cvs = [
        CvSource(row, len(find_placeholders(CvContent.model_validate(row.content))))
        for row in await documents.list_recent()
        if row.mode == "structured"
    ]
    return Sources(await profiles.list_recent(), cvs, await jobs.list_recent())


async def profile_application(
    profiles: ProfileRepository, profile_id: uuid.UUID
) -> ApplicationData:
    profile = await get_profile(profiles, profile_id)
    return to_application_data(CvContent.model_validate(profile.content))


async def document_application(
    documents: DocumentRepository, document_id: uuid.UUID
) -> ApplicationData:
    document = await get_document(documents, document_id)
    return to_application_data(CvContent.model_validate(document.content))


async def document_pdf(
    documents: DocumentRepository,
    jobs: JobRepository,
    renderer: RendererClient,
    document_id: uuid.UUID,
) -> rendering.Pdf:
    """The CV as a PDF to attach to an application, named for the job's company when it was
    tailored for one. Refused while placeholders remain, so a gap never reaches an employer."""
    pdf = await rendering.export_pdf(documents, renderer, document_id)
    document = await get_document(documents, document_id)
    job = await jobs.get(document.job_id) if document.job_id else None
    if job and job.company:
        name = CvContent.model_validate(document.content).basics.name
        return rendering.Pdf(pdf.content, rendering.pdf_filename(name, job.company))
    return pdf


async def save_job(
    jobs: JobRepository,
    *,
    description: str,
    title: str = "",
    company: str = "",
    url: str | None = None,
) -> tuple[Job, bool]:
    """Save the job ad the user is reading; True when it is new. Saving the same ad again (same
    URL) returns the job saved before, unchanged."""
    if url and (existing := await jobs.get_by_url(url)):
        return existing, False
    job = await job_service.create_job(
        jobs, description=description, title=title, company=company, url=url
    )
    return job, True
