"""The AI models users choose from, and the plan each needs (docs/PRODUCT.md, Plans and limits).

A model is a provider plus the model ids it uses: one for import and tailoring, and a small one for
job analysis. Model ids come from settings, so they change without code changes. Plan tags are
enforced while `ENFORCE_AI_PLANS` is on (the default).
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from api.billing.plans import Plan
from api.ports.llm.base import ProviderName

if TYPE_CHECKING:
    from api.settings import Settings


class AiModel(StrEnum):
    mimo_flash = "mimo-flash"
    claude_haiku = "claude-haiku"
    gemini_flash_lite = "gemini-flash-lite"
    claude_sonnet = "claude-sonnet"
    gemini_flash = "gemini-flash"
    mimo_pro = "mimo-pro"


@dataclass(frozen=True)
class ModelOption:
    id: AiModel
    label: str
    provider: ProviderName
    model: str
    """For import and tailoring."""
    analysis_model: str
    """For job analysis: the provider's small model."""
    plan: Plan


def model_options(settings: "Settings") -> list[ModelOption]:
    """Every model, free ones first, cheapest first within a plan."""
    claude, gemini, mimo = ProviderName.claude, ProviderName.gemini, ProviderName.mimo
    small = {
        claude: settings.claude_model_small,
        gemini: settings.gemini_model_small,
        mimo: settings.mimo_model_small,
    }
    rows: list[tuple[AiModel, str, ProviderName, str, Plan]] = [
        (AiModel.mimo_flash, "MiMo Flash", mimo, settings.mimo_model_small, "free"),
        (AiModel.claude_haiku, "Claude Haiku", claude, settings.claude_model_small, "free"),
        (
            AiModel.gemini_flash_lite,
            "Gemini Flash-Lite",
            gemini,
            settings.gemini_model_small,
            "free",
        ),
        (AiModel.mimo_pro, "MiMo Pro", mimo, settings.mimo_model_large, "pro"),
        (AiModel.gemini_flash, "Gemini Flash", gemini, settings.gemini_model_large, "pro"),
        (AiModel.claude_sonnet, "Claude Sonnet", claude, settings.claude_model_large, "pro"),
    ]
    return [
        ModelOption(
            id=id,
            label=label,
            provider=provider,
            model=model,
            analysis_model=small[provider],
            plan=plan,
        )
        for id, label, provider, model, plan in rows
    ]
