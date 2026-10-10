"""The Gemini adapter against a mocked Interactions API: request shape, parsing and errors."""

import base64
import json
from typing import Any

import httpx
import pytest
import respx
from google import genai
from google.genai import types
from pydantic import BaseModel

from api.errors import ProviderError, ProviderTimeout
from api.ports.llm.base import LLMRequest, ProviderName
from api.ports.llm.gemini import GeminiProvider
from cvcore.llm_schema import llm_schema

HOST = r".*googleapis\.com"


class Answer(BaseModel):
    name: str
    years: int


def interaction(text: str, status: str = "completed", **extra: Any) -> dict[str, Any]:
    return {
        "id": "int_1",
        "status": status,
        "model": "gemini-3.8-flash",
        "steps": [{"type": "model_output", "content": [{"type": "text", "text": text}]}],
        "usage": {
            "total_input_tokens": 900,
            "total_output_tokens": 200,
            "total_thought_tokens": 50,
        },
        **extra,
    }


def provider() -> GeminiProvider:
    # No retries in tests; the production client retries once.
    client = genai.Client(
        api_key="gemini-test",
        http_options=types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=0)),
    )
    return GeminiProvider("gemini-test", 90, client=client)


def request(**overrides: Any) -> LLMRequest[Answer]:
    values: dict[str, Any] = {
        "task": "tailor",
        "system": "You tailor.",
        "user_text": "Tailor this.",
        "output_model": Answer,
        "model": "gemini-3.8-flash",
    }
    return LLMRequest(**{**values, **overrides})


@respx.mock
async def test_sends_the_shared_schema_and_reads_the_answer() -> None:
    route = respx.route(host__regex=HOST).mock(
        return_value=httpx.Response(200, json=interaction('{"name": "Ada", "years": 9}'))
    )

    result = await provider().generate(request(effort="high"))

    assert result.output == Answer(name="Ada", years=9)
    assert (result.provider, result.model) == (ProviderName.gemini, "gemini-3.8-flash")
    # Thinking tokens are billed as output.
    assert (result.input_tokens, result.output_tokens) == (900, 250)
    body = json.loads(route.calls[0].request.content)
    assert body["model"] == "gemini-3.8-flash"
    assert body["system_instruction"] == "You tailor."
    assert body["input"] == {"type": "text", "text": "Tailor this."}
    assert body["store"] is False
    assert body["generation_config"] == {"max_output_tokens": 16000, "thinking_level": "high"}
    assert body["response_format"] == [
        {"type": "text", "mime_type": "application/json", "schema": llm_schema(Answer)}
    ]


@respx.mock
async def test_attaches_pdfs_before_the_text() -> None:
    route = respx.route(host__regex=HOST).mock(
        return_value=httpx.Response(200, json=interaction('{"name": "Ada", "years": 9}'))
    )

    await provider().generate(request(document=b"%PDF-1.7", model="gemini-3.5-flash-lite"))

    body = json.loads(route.calls[0].request.content)
    assert body["model"] == "gemini-3.5-flash-lite"
    # The SDK sends a list of parts as one user turn.
    assert body["input"] == [
        {
            "type": "user_input",
            "content": [
                {
                    "type": "document",
                    "data": base64.standard_b64encode(b"%PDF-1.7").decode(),
                    "mime_type": "application/pdf",
                },
                {"type": "text", "text": "Tailor this."},
            ],
        }
    ]


@respx.mock
async def test_missing_usage_counts_as_zero() -> None:
    reply = interaction('{"name": "Ada", "years": 9}')
    del reply["usage"]
    respx.route(host__regex=HOST).mock(return_value=httpx.Response(200, json=reply))

    result = await provider().generate(request())

    assert (result.input_tokens, result.output_tokens) == (0, 0)


@pytest.mark.parametrize(
    ("reply", "code"),
    [
        (interaction('{"name": "Ada"', status="incomplete"), "output_too_long"),
        (interaction("", status="failed"), "provider_error"),
        (interaction('{"name": "Ada"}'), "invalid_output"),
    ],
)
@respx.mock
async def test_unfinished_answers_are_provider_errors(reply: dict[str, Any], code: str) -> None:
    respx.route(host__regex=HOST).mock(return_value=httpx.Response(200, json=reply))

    with pytest.raises(ProviderError) as raised:
        await provider().generate(request())

    assert raised.value.details == {"provider": "gemini", "error_code": code}


@pytest.mark.parametrize(("status", "code"), [(429, "rate_limited"), (500, "provider_error")])
@respx.mock
async def test_http_errors_become_provider_errors(status: int, code: str) -> None:
    error = {"error": {"code": status, "message": "x", "status": "X"}}
    respx.route(host__regex=HOST).mock(return_value=httpx.Response(status, json=error))

    with pytest.raises(ProviderError) as raised:
        await provider().generate(request())

    assert raised.value.details["error_code"] == code
    assert raised.value.message.endswith("choose another model.")


@respx.mock
async def test_timeouts_become_provider_timeouts() -> None:
    respx.route(host__regex=HOST).mock(side_effect=httpx.ReadTimeout("slow"))

    with pytest.raises(ProviderTimeout) as raised:
        await provider().generate(request())

    assert raised.value.details == {"provider": "gemini", "error_code": "timeout"}


def test_the_default_client_is_built_from_the_key() -> None:
    assert GeminiProvider("gemini-test", 90).name == "gemini"
