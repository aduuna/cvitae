"""Gemini through google-genai's Interactions API, with the shared `llm_schema` as the response
schema. Interactions are not stored on Google's side (`store=False`)."""

import base64
import time

from google import genai
from google.genai import types
from google.genai._gaos.lib import compat_errors as errors  # the Interactions client's errors
from google.genai.interactions import ContentParam, Interaction, InteractionsInputParam
from pydantic import BaseModel, ValidationError

from api.ports.llm.base import (
    LLMRequest,
    LLMResult,
    ProviderName,
    provider_failure,
    provider_timeout,
)
from cvcore.llm_schema import llm_schema


class GeminiProvider:
    name = ProviderName.gemini

    def __init__(
        self,
        api_key: str,
        timeout_seconds: float,
        *,
        client: genai.Client | None = None,
    ) -> None:
        # `attempts=1` is one retry, with the SDK's jittered backoff.
        self._client = client or genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=1)),
        )
        self._timeout = timeout_seconds

    async def generate[T: BaseModel](self, request: LLMRequest[T]) -> LLMResult[T]:
        text: ContentParam = {"type": "text", "text": request.user_text}
        content: InteractionsInputParam = text
        if request.document is not None:
            document: ContentParam = {
                "type": "document",
                "data": base64.standard_b64encode(request.document).decode(),
                "mime_type": "application/pdf",
            }
            content = [document, text]

        started = time.monotonic()
        try:
            interaction = await self._client.aio.interactions.create(
                model=request.model,
                input=content,
                system_instruction=request.system,
                response_format=[
                    {
                        "type": "text",
                        "mime_type": "application/json",
                        "schema": llm_schema(request.output_model),
                    }
                ],
                generation_config={
                    "max_output_tokens": request.max_output_tokens,
                    "thinking_level": request.effort,
                },
                store=False,
                stream=False,
                timeout=self._timeout,
            )
        except errors.APITimeoutError as exc:
            raise provider_timeout(self.name) from exc
        except errors.RateLimitError as exc:
            raise provider_failure(self.name, "rate_limited", status=exc.status_code) from exc
        except errors.APIStatusError as exc:
            raise provider_failure(
                self.name, "provider_error", status=exc.status_code, reason=str(exc)
            ) from exc
        except errors.GeminiNextGenAPIClientError as exc:
            raise provider_failure(self.name, "provider_error", reason=type(exc).__name__) from exc

        if not isinstance(interaction, Interaction):  # pragma: no cover - stream=False
            raise provider_failure(self.name, "provider_error")
        if interaction.status == "incomplete":
            raise provider_failure(self.name, "output_too_long")
        if interaction.status != "completed":
            raise provider_failure(self.name, "provider_error")
        try:
            output = request.output_model.model_validate_json(interaction.output_text or "")
        except ValidationError as exc:
            raise provider_failure(self.name, "invalid_output") from exc
        usage = interaction.usage
        return LLMResult(
            output=output,
            provider=self.name,
            model=interaction.model or request.model,
            input_tokens=(usage.total_input_tokens or 0) if usage else 0,
            # Thinking is billed as output.
            output_tokens=((usage.total_output_tokens or 0) + (usage.total_thought_tokens or 0))
            if usage
            else 0,
            duration_ms=int((time.monotonic() - started) * 1000),
        )
