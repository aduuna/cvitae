"""Account export and deletion (docs/PRODUCT.md, Settings; docs/BACKEND.md, REST API).

Export gathers everything the account holds. Deletion removes the user's row, which takes every
user-owned row with it (ON DELETE CASCADE), and the user's files in storage. Neither logs content:
only the user's id and counts."""

import logging
import uuid
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from api.db.models import (
    AiRun,
    Document,
    DocumentVersion,
    ExtensionToken,
    Job,
    Profile,
    Subscription,
    Upload,
    User,
    UserTemplate,
)
from api.errors import Conflict, ValidationFailed
from api.ports.storage import Storage
from api.repositories.ai_runs import AiRunRepository
from api.repositories.documents import DocumentRepository, DocumentVersionRepository
from api.repositories.extension_tokens import ExtensionTokenRepository
from api.repositories.jobs import JobRepository
from api.repositories.profiles import ProfileRepository
from api.repositories.subscriptions import SubscriptionRepository
from api.repositories.uploads import UploadRepository
from api.repositories.user_templates import UserTemplateRepository
from api.repositories.users import UserRepository
from api.services.uploads import user_prefix

logger = logging.getLogger(__name__)

CHARGING = ("active", "attention")
"""Subscription statuses that Paystack keeps charging. Deleting the account would drop the row
that ties webhooks to the user, and the charges would go on with nothing to cancel them."""


@dataclass(frozen=True)
class AccountRepositories:
    """The signed-in user's repositories, one per table that holds their data."""

    profiles: ProfileRepository
    jobs: JobRepository
    documents: DocumentRepository
    versions: DocumentVersionRepository
    templates: UserTemplateRepository
    uploads: UploadRepository
    ai_runs: AiRunRepository
    subscriptions: SubscriptionRepository
    connections: ExtensionTokenRepository


@dataclass(frozen=True)
class AccountData:
    """Everything an account holds, as rows. Upload bytes are not included, only what is known
    about each file; extension tokens are not data (only a hash of each is kept)."""

    user: User
    profiles: Sequence[Profile]
    jobs: Sequence[Job]
    documents: Sequence[Document]
    versions: Mapping[uuid.UUID, Sequence[DocumentVersion]]
    """By document id, oldest first."""
    templates: Sequence[UserTemplate]
    uploads: Sequence[Upload]
    ai_runs: Sequence[AiRun]
    subscription: Subscription | None
    connections: Sequence[ExtensionToken]


async def export_account(user: User, repositories: AccountRepositories) -> AccountData:
    versions: dict[uuid.UUID, list[DocumentVersion]] = defaultdict(list)
    for version in await repositories.versions.list(
        DocumentVersion.document_id.asc(), DocumentVersion.number.asc()
    ):
        versions[version.document_id].append(version)
    data = AccountData(
        user=user,
        profiles=await repositories.profiles.list(Profile.created_at.asc()),
        jobs=await repositories.jobs.list(Job.created_at.asc()),
        documents=await repositories.documents.list(Document.created_at.asc()),
        versions=versions,
        templates=await repositories.templates.list(UserTemplate.created_at.asc()),
        uploads=await repositories.uploads.list(Upload.created_at.asc()),
        ai_runs=await repositories.ai_runs.list(AiRun.created_at.asc()),
        subscription=await repositories.subscriptions.current(),
        connections=await repositories.connections.list(ExtensionToken.created_at.asc()),
    )
    logger.info(
        "account exported",
        extra={
            "user_id": str(user.id),
            "profiles": len(data.profiles),
            "documents": len(data.documents),
            "jobs": len(data.jobs),
        },
    )
    return data


async def delete_account(
    users: UserRepository,
    subscriptions: SubscriptionRepository,
    storage: Storage,
    user: User,
    confirmation: str,
) -> None:
    """Delete the account after the user typed their email address. The rows go first, inside
    the request's transaction: if clearing storage then fails, the request rolls back and the
    account is whole, ready for another try."""
    if confirmation.strip().lower() != user.email.strip().lower():
        raise ValidationFailed(
            "Type the email address of this account to confirm.", {"field": "email"}
        )
    subscription = await subscriptions.current()
    if subscription is not None and subscription.status in CHARGING:
        raise Conflict(
            "Cancel your Pro subscription first: use Manage subscription under Billing. "
            "Then delete your account."
        )
    await users.delete(user.id)
    files = await storage.delete_prefix(user_prefix(user.id))
    logger.info("account deleted", extra={"user_id": str(user.id), "files": files})
