"""Which AI model runs a request: the one asked for, else the user's choice, else the default."""

from dataclasses import dataclass

from api.ai.models import AiModel, ModelOption
from api.billing.plans import Plan
from api.db.models import User
from api.errors import ClaudeUnavailable, PlanRequired, ServiceUnavailable, ValidationFailed
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


CLAUDE_MODELS = (AiModel.claude_sonnet, AiModel.claude_haiku)
"""Best first: what a Claude-only task prefers when the user has not chosen a Claude model."""


def choose_claude_model(
    registry: ProviderRegistry, user: User, *, enforce_plans: bool, plan: Plan
) -> ModelChoice:
    """For tasks that always run on Claude, whatever model the user chose for the others (custom
    templates: the fidelity of a design and the quality of the Typst matter most). The user's
    own Claude model when they chose one, else the best Claude model their plan includes
    (Sonnet on Pro, Haiku on Free). Raises ClaudeUnavailable without an Anthropic key."""
    usable = [
        option
        for model in CLAUDE_MODELS
        if (option := registry.option(model))
        and (not enforce_plans or option.plan == "free" or plan == "pro")
    ]
    if not usable:
        raise ClaudeUnavailable(
            "Drafting a template needs Claude, which is not set up on this server yet."
        )
    option = next((o for o in usable if o.id == user.preferred_ai_model), usable[0])
    return ModelChoice(option=option, provider=registry.provider(option))
