"""Claude through the Anthropic SDK: structured output with the Pydantic model (`parse`)."""

import base64
import time
from typing import Any

import anthropic
from anthropic.types.beta import (
    BetaContentBlockParam,
    BetaRequestDocumentBlockParam,
    BetaTextBlockParam,
)
from pydantic import BaseModel, ValidationError

from api.ports.llm.base import (
    LLMRequest,
    LLMResult,
    ProviderName,
    provider_failure,
    provider_timeout,
)

# On a safety decline the API re-runs the request on a fallback model in the same call. Haiku has
# no server-side fallback, so only the models listed here send it.
FALLBACK_BETA = "server-side-fallback-2026-07-01"


def _reason(body: object) -> str | None:
    """The message of an Anthropic error body: {"error": {"type": ..., "message": ...}}."""
    error = body.get("error") if isinstance(body, dict) else None
    if isinstance(error, dict):
        return f"{error.get('type')}: {error.get('message')}"
    return None


class ClaudeProvider:
    name = ProviderName.claude

    def __init__(
        self,
        api_key: str,
        timeout_seconds: float,
        *,
        fallback_models: frozenset[str] = frozenset(),
        client: anthropic.AsyncAnthropic | None = None,
    ) -> None:
        # One retry on rate limits, 5xx and connection errors; the SDK backs off with jitter.
        self._client = client or anthropic.AsyncAnthropic(
            api_key=api_key, timeout=timeout_seconds, max_retries=1
        )
        self._fallback_models = fallback_models

    async def generate[T: BaseModel](self, request: LLMRequest[T]) -> LLMResult[T]:
        content: list[BetaContentBlockParam] = []
        if request.document is not None:
            content.append(
                BetaRequestDocumentBlockParam(
                    type="document",
                    source={
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": base64.standard_b64encode(request.document).decode(),
                    },
                )
            )
        content.append(BetaTextBlockParam(type="text", text=request.user_text))
        extra: dict[str, Any] = {}
        if request.model in self._fallback_models:
            extra = {"betas": [FALLBACK_BETA], "fallbacks": "default"}

        started = time.monotonic()
        try:
            response = await self._client.beta.messages.parse(
                model=request.model,
                max_tokens=request.max_output_tokens,
                system=request.system,
                messages=[{"role": "user", "content": content}],
                output_format=request.output_model,
                output_config={"effort": request.effort},
                **extra,
            )
        except anthropic.APITimeoutError as exc:
            raise provider_timeout(self.name) from exc
        except anthropic.RateLimitError as exc:
            raise provider_failure(self.name, "rate_limited", status=exc.status_code) from exc
        except anthropic.APIStatusError as exc:
            raise provider_failure(
                self.name, "provider_error", status=exc.status_code, reason=_reason(exc.body)
            ) from exc
        except anthropic.APIConnectionError as exc:
            raise provider_failure(self.name, "provider_error", reason="connection failed") from exc
        except ValidationError as exc:
            raise provider_failure(self.name, "invalid_output") from exc

        if response.stop_reason == "refusal":
            raise provider_failure(self.name, "refused")
        if response.stop_reason == "max_tokens":
            raise provider_failure(self.name, "output_too_long")
        output = response.parsed_output
        if output is None:
            raise provider_failure(self.name, "invalid_output")
        return LLMResult(
            output=output,
            provider=self.name,
            model=response.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            duration_ms=int((time.monotonic() - started) * 1000),
        )
