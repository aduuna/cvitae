"""The Claude adapter against a mocked Messages API: request shape, parsing and error mapping."""

import base64
import json
from collections.abc import Callable
from typing import Any

import anthropic
import httpx2
import pytest
from pydantic import BaseModel

from api.errors import ProviderError, ProviderTimeout
from api.ports.llm.base import LLMRequest, ProviderName
from api.ports.llm.claude import FALLBACK_BETA, ClaudeProvider


class Answer(BaseModel):
    name: str
    years: int


def message(text: str, stop_reason: str = "end_turn", model: str = "claude-sonnet-5-5") -> Any:
    return {
        "id": "msg_1",
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": [{"type": "text", "text": text}],
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {"input_tokens": 1200, "output_tokens": 340},
    }


def provider_for(
    handler: Callable[[httpx2.Request], httpx2.Response], seen: list[httpx2.Request] | None = None
) -> ClaudeProvider:
    def record(request: httpx2.Request) -> httpx2.Response:
        if seen is not None:
            seen.append(request)
        return handler(request)

    client = anthropic.AsyncAnthropic(
        api_key="sk-ant-test",
        max_retries=0,
        http_client=anthropic.DefaultAsyncHttpxClient(transport=httpx2.MockTransport(record)),
    )
    return ClaudeProvider(
        "sk-ant-test", 90, fallback_models=frozenset({"claude-sonnet-5-5"}), client=client
    )


def request(**overrides: Any) -> LLMRequest[Answer]:
    values: dict[str, Any] = {
        "task": "import",
        "system": "You extract.",
        "user_text": "Extract this.",
        "output_model": Answer,
        "model": "claude-sonnet-5-5",
    }
    return LLMRequest(**{**values, **overrides})


async def test_sends_a_structured_request_with_fallback() -> None:
    seen: list[httpx2.Request] = []
    provider = provider_for(
        lambda _: httpx2.Response(200, json=message('{"name": "Ada", "years": 9}')), seen
    )

    result = await provider.generate(request(document=b"%PDF-1.7 bytes", effort="low"))

    assert result.output == Answer(name="Ada", years=9)
    assert (result.provider, result.model) == (ProviderName.claude, "claude-sonnet-5-5")
    assert (result.input_tokens, result.output_tokens) == (1200, 340)
    body = json.loads(seen[0].content)
    assert seen[0].headers["anthropic-beta"] == FALLBACK_BETA
    assert body["model"] == "claude-sonnet-5-5"
    assert body["system"] == "You extract."
    assert body["fallbacks"] == "default"
    assert body["output_config"]["effort"] == "low"
    assert body["output_config"]["format"]["type"] == "json_schema"
    document, text = body["messages"][0]["content"]
    assert document["source"] == {
        "type": "base64",
        "media_type": "application/pdf",
        "data": base64.standard_b64encode(b"%PDF-1.7 bytes").decode(),
    }
    assert text == {"type": "text", "text": "Extract this."}


async def test_models_without_a_fallback_do_not_send_one() -> None:
    seen: list[httpx2.Request] = []
    reply = message('{"name": "Ada", "years": 9}', model="claude-haiku-5-5")
    provider = provider_for(lambda _: httpx2.Response(200, json=reply), seen)

    result = await provider.generate(request(model="claude-haiku-5-5"))

    body = json.loads(seen[0].content)
    assert body["model"] == "claude-haiku-5-5"
    assert "fallbacks" not in body
    assert "anthropic-beta" not in seen[0].headers
    assert result.model == "claude-haiku-5-5"


async def test_records_the_model_that_answered_after_a_fallback() -> None:
    reply = message('{"name": "Ada", "years": 9}', model="claude-opus-5-5")
    provider = provider_for(lambda _: httpx2.Response(200, json=reply))

    assert (await provider.generate(request())).model == "claude-opus-5-5"


@pytest.mark.parametrize(
    ("stop_reason", "code"), [("refusal", "refused"), ("max_tokens", "output_too_long")]
)
async def test_unfinished_answers_are_provider_errors(stop_reason: str, code: str) -> None:
    reply = message('{"name": "Ada", "years": 9}', stop_reason=stop_reason)
    provider = provider_for(lambda _: httpx2.Response(200, json=reply))

    with pytest.raises(ProviderError) as raised:
        await provider.generate(request())

    assert raised.value.details == {"provider": "claude", "error_code": code}


async def test_unreadable_output_is_a_provider_error() -> None:
    provider = provider_for(lambda _: httpx2.Response(200, json=message('{"name": "Ada"}')))

    with pytest.raises(ProviderError) as raised:
        await provider.generate(request())

    assert raised.value.details["error_code"] == "invalid_output"
    assert raised.value.message == "Claude returned something we could not read. Try again."


@pytest.mark.parametrize(
    ("status", "code", "message_start"),
    [
        (429, "rate_limited", "Claude is busy right now."),
        (500, "provider_error", "Claude could not finish this request."),
        (401, "provider_error", "Claude could not finish this request."),
    ],
)
async def test_http_errors_become_provider_errors(
    status: int, code: str, message_start: str
) -> None:
    error = {"type": "error", "error": {"type": "api_error", "message": "x"}}
    provider = provider_for(lambda _: httpx2.Response(status, json=error))

    with pytest.raises(ProviderError) as raised:
        await provider.generate(request())

    assert raised.value.details["error_code"] == code
    assert raised.value.details["provider_status"] == status
    assert raised.value.message.startswith(message_start)
    assert raised.value.message.endswith("choose another model.")


async def test_timeouts_become_provider_timeouts() -> None:
    def slow(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ReadTimeout("slow", request=request)

    with pytest.raises(ProviderTimeout) as raised:
        await provider_for(slow).generate(request())

    assert raised.value.details == {"provider": "claude", "error_code": "timeout"}


async def test_connection_failures_are_provider_errors() -> None:
    def down(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("down", request=request)

    with pytest.raises(ProviderError):
        await provider_for(down).generate(request())


def test_the_default_client_retries_once() -> None:
    provider = ClaudeProvider("sk-ant-test", 90)

    assert provider._client.max_retries == 1
