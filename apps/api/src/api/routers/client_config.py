"""What the SPA needs before anyone signs in: how to sign in. Public; nothing here is secret."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from api.ai.models import AiModel
from api.billing.plans import PLANS, Plan
from api.deps import AppSettings, Providers
from api.ports.llm.base import ProviderName

router = APIRouter(prefix="/client-config", tags=["client-config"])


class FirebaseConfig(BaseModel):
    api_key: str
    auth_domain: str
    project_id: str
    app_id: str


class AiModelInfo(BaseModel):
    id: AiModel
    label: str
    provider: ProviderName
    plan: Plan
    """Pro models need the Pro plan when `plans_enforced` is true."""


class PlanInfo(BaseModel):
    id: Plan
    label: str
    documents: int
    profiles: int
    ai_runs: int
    """Per calendar month (UTC)."""


class ClientConfig(BaseModel):
    auth_mode: Literal["firebase", "dev"]
    firebase: FirebaseConfig | None
    """Set when auth_mode is firebase."""
    ai_models: list[AiModelInfo]
    """The AI models this server offers, free first."""
    default_ai_model: AiModel | None
    """Used when a user has not chosen one; None when no model is offered."""
    plans_enforced: bool
    plans: list[PlanInfo]
    billing_enabled: bool
    """Whether a Free user can upgrade on this server."""


@router.get("")
async def get_client_config(settings: AppSettings, providers: Providers) -> ClientConfig:
    firebase = None
    if settings.auth_mode == "firebase":
        firebase = FirebaseConfig(
            api_key=settings.firebase_api_key or "",
            auth_domain=settings.firebase_auth_domain or "",
            project_id=settings.firebase_project_id or "",
            app_id=settings.firebase_app_id or "",
        )
    models = [
        AiModelInfo(id=o.id, label=o.label, provider=o.provider, plan=o.plan)
        for o in providers.options
    ]
    offered = {model.id for model in models}
    default = settings.default_ai_model
    return ClientConfig(
        auth_mode=settings.auth_mode,
        firebase=firebase,
        ai_models=models,
        default_ai_model=default if default in offered else (models[0].id if models else None),
        plans_enforced=settings.enforce_ai_plans,
        plans=[
            PlanInfo(
                id=p.id,
                label=p.label,
                documents=p.documents,
                profiles=p.profiles,
                ai_runs=p.ai_runs,
            )
            for p in PLANS.values()
        ],
        billing_enabled=settings.billing_enabled,
    )
