"""The LLM port: one request and result shape for every provider (docs/BACKEND.md, AI pipeline).

Prompts, schemas, validation and the fact guard are shared; adapters only translate requests.
"""

import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal, Protocol

from pydantic import BaseModel

from api.errors import ProviderError, ProviderTimeout

logger = logging.getLogger(__name__)

AiTask = Literal["import", "analyze_job", "tailor"]
Effort = Literal["low", "medium", "high"]


class ProviderName(StrEnum):
    claude = "claude"
    gemini = "gemini"
    mimo = "mimo"


PROVIDER_LABELS = {
    ProviderName.claude: "Claude",
    ProviderName.gemini: "Gemini",
    ProviderName.mimo: "MiMo",
}


@dataclass(frozen=True)
class LLMRequest[T: BaseModel]:
    task: AiTask
    system: str
    user_text: str
    output_model: type[T]
    """The provider must return a valid instance of this model."""
    model: str
    """The provider's model id, from the AI model the user chose (api.ai.models)."""
    document: bytes | None = None
    """PDF bytes, for import."""
    effort: Effort = "medium"
    max_output_tokens: int = 16000


@dataclass(frozen=True)
class LLMResult[T: BaseModel]:
    output: T
    provider: ProviderName
    model: str
    """The model that answered, which can differ from the one asked for after a fallback."""
    input_tokens: int
    output_tokens: int
    duration_ms: int


class LLMProvider(Protocol):
    name: ProviderName

    async def generate[T: BaseModel](self, request: LLMRequest[T]) -> LLMResult[T]: ...


def provider_failure(
    provider: ProviderName,
    error_code: str,
    *,
    status: int | None = None,
    reason: str | None = None,
) -> ProviderError:
    """The error every adapter raises when a call fails; `error_code` goes on the ai_runs row.
    `status` and `reason` (the provider's HTTP status and its own error message, which never
    contains prompt content) are logged so a failure can be diagnosed without the payload."""
    if status is not None or reason:
        logger.warning(
            "ai provider call failed",
            extra={
                "provider": str(provider),
                "error_code": error_code,
                "provider_status": status,
                "provider_reason": (reason or "")[:300],
            },
        )
    name = PROVIDER_LABELS[provider]
    messages = {
        "rate_limited": f"{name} is busy right now. Wait a minute, or choose another model.",
        "refused": f"{name} declined this request. Choose another model and try again.",
        "output_too_long": f"{name} ran out of room before finishing. Try again.",
        "invalid_output": f"{name} returned something we could not read. Try again.",
    }
    message = messages.get(
        error_code, f"{name} could not finish this request. Try again, or choose another model."
    )
    details: dict[str, object] = {"provider": str(provider), "error_code": error_code}
    if status is not None:
        details["provider_status"] = status
    return ProviderError(message, details)


def provider_timeout(provider: ProviderName) -> ProviderTimeout:
    name = PROVIDER_LABELS[provider]
    return ProviderTimeout(
        f"{name} took too long to answer. Try again, or choose another model.",
        {"provider": str(provider), "error_code": "timeout"},
    )
