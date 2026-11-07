"""Routes for Google Cloud Scheduler. No Firebase auth: an OIDC token from the scheduler's service
account is the only way in (`deps.scheduler_call`)."""

from fastapi import APIRouter
from pydantic import BaseModel

from api.db.base import utcnow
from api.deps import SchedulerCall, VersionPrunerDep
from api.errors import ErrorEnvelope
from api.services import versions

router = APIRouter(
    prefix="/internal",
    tags=["internal"],
    dependencies=[SchedulerCall],
    responses={
        401: {"model": ErrorEnvelope, "description": "No valid Google ID token"},
        403: {"model": ErrorEnvelope, "description": "The token is not the scheduler's"},
        503: {"model": ErrorEnvelope, "description": "Scheduled jobs are not set up"},
    },
)


class Pruned(BaseModel):
    deleted: int
    """Autosave versions removed."""


@router.post("/prune-versions")
async def prune_versions(pruner: VersionPrunerDep) -> Pruned:
    """Delete autosave versions older than 7 days."""
    return Pruned(deleted=await versions.prune_autosaves(pruner, utcnow()))
