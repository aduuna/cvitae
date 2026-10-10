"""FastAPI dependencies: the only place where ports and repositories are wired."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import User
from api.ports.auth import AuthVerifier
from api.ports.renderer import RendererClient
from api.repositories.documents import DocumentRepository, DocumentVersionRepository
from api.repositories.profiles import ProfileRepository
from api.repositories.users import UserRepository
from api.services.users import ensure_user


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """One transaction per request, committed when the route returns without error."""
    async with request.app.state.sessions() as session:
        try:
            yield session
            await session.commit()
        except BaseException:
            await session.rollback()
            raise


# scope="function": commit before the response is sent, so a failed commit is a failed request.
Session = Annotated[AsyncSession, Depends(get_session, scope="function")]


def get_auth_verifier(request: Request) -> AuthVerifier:
    return request.app.state.auth_verifier


def get_renderer(request: Request) -> RendererClient:
    return request.app.state.renderer


Renderer = Annotated[RendererClient, Depends(get_renderer)]


async def current_user(
    request: Request,
    session: Session,
    verifier: Annotated[AuthVerifier, Depends(get_auth_verifier)],
) -> User:
    identity = await verifier.verify(request)
    return await ensure_user(UserRepository(session), identity)


CurrentUser = Annotated[User, Depends(current_user)]


def get_profiles(session: Session, user: CurrentUser) -> ProfileRepository:
    return ProfileRepository(session, user.id)


def get_documents(session: Session, user: CurrentUser) -> DocumentRepository:
    return DocumentRepository(session, user.id)


def get_versions(session: Session, user: CurrentUser) -> DocumentVersionRepository:
    return DocumentVersionRepository(session, user.id)


Profiles = Annotated[ProfileRepository, Depends(get_profiles)]
Documents = Annotated[DocumentRepository, Depends(get_documents)]
Versions = Annotated[DocumentVersionRepository, Depends(get_versions)]
