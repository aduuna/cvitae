"""MiMo (Xiaomi) through its OpenAI-compatible Chat Completions endpoint, with httpx.

Structured output uses the shared llm_schema as a strict json_schema. MiMo reads images but not
PDFs, so PDF pages are rendered to PNG first. Its Anthropic-compatible endpoint is not used: it
ignores structured output and drops PDF documents. Thinking stays on: without it, extraction drops
bullets.
"""

import asyncio
import base64
import random
import time
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from api.ports.llm.base import (
    LLMRequest,
    LLMResult,
    ProviderName,
    provider_failure,
    provider_timeout,
)
from api.ports.llm.pages import pdf_to_pngs
from cvcore.llm_schema import llm_schema

BASE_URL = "https://api.xiaomimimo.com/v1"
RETRY_STATUSES = {429, 500, 502, 503, 504}


class MimoProvider:
    name = ProviderName.mimo

    def __init__(
        self,
        api_key: str,
        timeout_seconds: float,
        *,
        base_url: str = BASE_URL,
        client: httpx.AsyncClient | None = None,
        retry_delay: float = 1.0,
    ) -> None:
        self._client = client or httpx.AsyncClient(base_url=base_url, timeout=timeout_seconds)
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._retry_delay = retry_delay

    async def _messages(self, request: LLMRequest[Any]) -> list[dict[str, Any]]:
        user: Any = request.user_text
        if request.document is not None:
            pages = await asyncio.to_thread(pdf_to_pngs, request.document)
            user = [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{base64.b64encode(p).decode()}"},
                }
                for p in pages
            ] + [{"type": "text", "text": request.user_text}]
        return [{"role": "system", "content": request.system}, {"role": "user", "content": user}]

    async def _post(self, body: dict[str, Any]) -> httpx.Response:
        """One retry, with jitter, on rate limits, 5xx and dropped connections."""
        for attempt in range(2):
            last = attempt == 1
            try:
                response = await self._client.post(
                    "/chat/completions", json=body, headers=self._headers
                )
            except httpx.TimeoutException as exc:
                raise provider_timeout(self.name) from exc
            except httpx.TransportError as exc:
                if last:
                    raise provider_failure(
                        self.name, "provider_error", reason=type(exc).__name__
                    ) from exc
            else:
                if response.status_code not in RETRY_STATUSES or last:
                    return response
            await asyncio.sleep(self._retry_delay * (0.5 + random.random()))  # noqa: S311
        raise AssertionError("unreachable")  # pragma: no cover

    async def generate[T: BaseModel](self, request: LLMRequest[T]) -> LLMResult[T]:
        body = {
            "model": request.model,
            "max_tokens": request.max_output_tokens,
            "messages": await self._messages(request),
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": request.output_model.__name__,
                    "strict": True,
                    "schema": llm_schema(request.output_model),
                },
            },
        }
        started = time.monotonic()
        response = await self._post(body)
        if response.status_code != 200:
            error = _error(response)
            code = "rate_limited" if response.status_code == 429 else "provider_error"
            raise provider_failure(self.name, code, status=response.status_code, reason=error)

        data = response.json()
        choice = data["choices"][0]
        if choice.get("finish_reason") == "length":
            raise provider_failure(self.name, "output_too_long")
        if choice.get("finish_reason") == "content_filter":
            raise provider_failure(self.name, "refused")
        try:
            output = request.output_model.model_validate_json(choice["message"]["content"] or "")
        except ValidationError as exc:
            raise provider_failure(self.name, "invalid_output") from exc
        usage = data.get("usage") or {}
        return LLMResult(
            output=output,
            provider=self.name,
            model=data.get("model") or request.model,
            input_tokens=usage.get("prompt_tokens", 0),
            # Includes reasoning tokens, which are billed as output.
            output_tokens=usage.get("completion_tokens", 0),
            duration_ms=int((time.monotonic() - started) * 1000),
        )


def _error(response: httpx.Response) -> str | None:
    try:
        error = response.json().get("error", {})
    except ValueError:
        return None
    return f"{error.get('type')}: {error.get('message')}" if isinstance(error, dict) else None
