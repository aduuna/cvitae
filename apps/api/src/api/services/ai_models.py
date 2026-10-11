"""Which AI model runs a request: the one asked for, else the user's choice, else the default."""

from dataclasses import dataclass

from api.ai.models import AiModel, ModelOption
from api.billing.plans import Plan
from api.db.models import User
from api.errors import PlanRequired, ServiceUnavailable, ValidationFailed
from api.ports.llm.base import LLMProvider
from api.ports.llm.registry import ProviderRegistry


@dataclass(frozen=True)
class ModelChoice:
    option: ModelOption
    provider: LLMProvider


def preferred_model(registry: ProviderRegistry, user: User, default: AiModel) -> AiModel | None:
    """The user's saved model while it is offered, else the default, else the first offered."""
    for candidate in (user.preferred_ai_model, default):
        if candidate and registry.option(AiModel(candidate)):
            return AiModel(candidate)
    return registry.options[0].id if registry.options else None


def choose_model(
    registry: ProviderRegistry,
    user: User,
    requested: AiModel | None,
    *,
    default: AiModel,
    enforce_plans: bool,
    plan: Plan,
) -> ModelChoice:
    """`plan` is the user's current plan (services.billing.current_plan)."""
    model = requested or preferred_model(registry, user, default)
    if model is None:
        raise ServiceUnavailable("AI is not set up on this server yet.")
    option = registry.option(model)
    if option is None:
        raise ValidationFailed(
            "This AI model is not available on this server. Choose another model.",
            {"field": "ai_model"},
        )
    if enforce_plans and option.plan == "pro" and plan != "pro":
        raise PlanRequired(
            f"{option.label} is part of Pro. Upgrade to use it, or choose a free model.",
            {"ai_model": str(option.id)},
        )
    return ModelChoice(option=option, provider=registry.provider(option))
