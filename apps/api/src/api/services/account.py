"""Account export and deletion (docs/PRODUCT.md, Settings; docs/BACKEND.md, REST API).

Export gathers everything the account holds. Deletion removes the user's row, which takes every
user-owned row with it (ON DELETE CASCADE), commits that, and then clears the user's files in
storage. The database and storage cannot be changed together, so the rows are the point of no
return and the files follow them. Neither logs content: only the user's id, counts and error
codes."""

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
    """Delete the account after the user typed their email address.

    The rows are deleted and committed first, then the files. Storage cannot join the database's
    transaction (a bucket deletes object by object), so undoing the rows after a storage failure
    would bring back upload rows whose files are already gone. Once the rows are committed the
    account no longer exists, so a storage failure does not fail the request: it is logged (the
    user's id and an error code, never content) at error severity, and the objects left under
    `uploads/<user_id>/` are for a sweep to remove, since nothing in the database points at them
    any more."""
    if confirmation.strip().lower() != user.email.strip().lower():
        raise ValidationFailed(
            "Type the email address of this account to confirm.", {"field": "email"}
        )
    subscription = await subscriptions.current()
    if subscription is not None and subscription.status in CHARGING:
        if subscription.paystack_subscription_code is None:
            # Paystack has not confirmed the subscription yet, so there is nothing to manage.
            raise Conflict(
                "Paystack is still setting up your Pro subscription, so it cannot be cancelled "
                "yet. Try again in a few minutes.",
                {"reason": "subscription_pending"},
            )
        raise Conflict(
            "Cancel your Pro subscription first: use Manage subscription under Billing. "
            "Then delete your account.",
            {"reason": "subscription_active"},
        )
    await users.delete(user.id)
    await users.commit()
    try:
        files = await storage.delete_prefix(user_prefix(user.id))
    except Exception as exc:
        logger.error(
            "account deleted, its files were not removed",
            extra={"user_id": str(user.id), "error": getattr(exc, "code", type(exc).__name__)},
        )
        return
    logger.info("account deleted", extra={"user_id": str(user.id), "files": files})
