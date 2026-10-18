"""FastAPI dependencies: the only place where ports and repositories are wired."""

import uuid
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from api.billing.plans import Plan
from api.db.models import User
from api.errors import ServiceUnavailable
from api.ports.auth import AuthVerifier
from api.ports.llm.registry import ProviderRegistry
from api.ports.renderer import RendererClient
from api.ports.storage import Storage
from api.repositories.ai_runs import AiRunRepository
from api.repositories.documents import DocumentRepository, DocumentVersionRepository
from api.repositories.jobs import JobRepository
from api.repositories.profiles import ProfileRepository
from api.repositories.subscriptions import SubscriptionRepository
from api.repositories.uploads import UploadRepository
from api.repositories.users import UserRepository
from api.repositories.webhooks import WebhookRepository
from api.services import billing
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


def get_providers(request: Request) -> ProviderRegistry:
    return request.app.state.providers


Providers = Annotated[ProviderRegistry, Depends(get_providers)]


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


AppSettings = Annotated[Settings, Depends(get_settings)]


def get_billing(request: Request) -> billing.Billing:
    setup: billing.Billing | None = request.app.state.billing
    if setup is None:
        raise ServiceUnavailable("Upgrades are not available on this server yet.")
    return setup


BillingSetup = Annotated[billing.Billing, Depends(get_billing)]


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


def get_jobs(session: Session, user: CurrentUser) -> JobRepository:
    return JobRepository(session, user.id)


def get_uploads(session: Session, user: CurrentUser) -> UploadRepository:
    return UploadRepository(session, user.id)


def get_ai_runs(session: Session, user: CurrentUser) -> AiRunRepository:
    return AiRunRepository(session, user.id)


def get_subscriptions(session: Session, user: CurrentUser) -> SubscriptionRepository:
    return SubscriptionRepository(session, user.id)


def get_subscriptions_for(session: Session) -> billing.SubscriptionsFor:
    """For webhooks, which are about a user found from the event, not a signed-in one."""

    def scoped(user_id: uuid.UUID) -> SubscriptionRepository:
        return SubscriptionRepository(session, user_id)

    return scoped


def get_webhooks(session: Session) -> WebhookRepository:
    return WebhookRepository(session)


Profiles = Annotated[ProfileRepository, Depends(get_profiles)]
Documents = Annotated[DocumentRepository, Depends(get_documents)]
Versions = Annotated[DocumentVersionRepository, Depends(get_versions)]
Jobs = Annotated[JobRepository, Depends(get_jobs)]
Uploads = Annotated[UploadRepository, Depends(get_uploads)]
AiRuns = Annotated[AiRunRepository, Depends(get_ai_runs)]
Subscriptions = Annotated[SubscriptionRepository, Depends(get_subscriptions)]
SubscriptionsFor = Annotated[billing.SubscriptionsFor, Depends(get_subscriptions_for)]
Webhooks = Annotated[WebhookRepository, Depends(get_webhooks)]


async def get_plan(user: CurrentUser, subscriptions: Subscriptions, settings: AppSettings) -> Plan:
    """The plan the signed-in user is on now; DEV_PLAN overrides it on a local stack."""
    return settings.dev_plan or await billing.current_plan(user, subscriptions)


UserPlan = Annotated[Plan, Depends(get_plan)]
