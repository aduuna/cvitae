"""FastAPI dependencies: the only place where ports and repositories are wired."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import User
from api.ports.auth import AuthVerifier
from api.ports.renderer import RendererClient
from api.ports.storage import Storage
from api.repositories.documents import DocumentRepository, DocumentVersionRepository
from api.repositories.profiles import ProfileRepository
from api.repositories.users import UserRepository
from api.services.users import ensure_user
from api.settings import Settings


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


def get_storage(request: Request) -> Storage:
    return request.app.state.storage


FileStorage = Annotated[Storage, Depends(get_storage)]


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


AppSettings = Annotated[Settings, Depends(get_settings)]


def get_users(session: Session) -> UserRepository:
    return UserRepository(session)


Users = Annotated[UserRepository, Depends(get_users)]


async def current_user(
    request: Request,
    users: Users,
    verifier: Annotated[AuthVerifier, Depends(get_auth_verifier)],
) -> User:
    identity = await verifier.verify(request)
    return await ensure_user(users, identity)


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
