"""The MiMo adapter against a mocked Chat Completions endpoint, and PDF pages as images."""

import base64
import json
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from pydantic import BaseModel

from api.errors import ProviderError, ProviderTimeout, ValidationFailed
from api.ports.llm.base import LLMRequest, ProviderName
from api.ports.llm.mimo import BASE_URL, MimoProvider
from api.ports.llm.pages import pdf_to_pngs
from cvcore.llm_schema import llm_schema

FIXTURES = Path(__file__).resolve().parents[3] / "templates" / "fixtures"
SAMPLE_PDF = (FIXTURES / "sample-cv.pdf").read_bytes()
URL = f"{BASE_URL}/chat/completions"
PNG = b"\x89PNG\r\n\x1a\n"


class Answer(BaseModel):
    name: str
    years: int


def completion(content: str, finish_reason: str = "stop") -> dict[str, Any]:
    return {
        "model": "mimo-v2.6-flash",
        "choices": [{"message": {"content": content}, "finish_reason": finish_reason}],
        "usage": {
            "prompt_tokens": 2400,
            "completion_tokens": 3700,
            "completion_tokens_details": {"reasoning_tokens": 1500},
        },
    }


def provider() -> MimoProvider:
    return MimoProvider("sk-mimo-test", 180, retry_delay=0)


def request(**overrides: Any) -> LLMRequest[Answer]:
    values: dict[str, Any] = {
        "task": "import",
        "system": "You extract.",
        "user_text": "Extract this.",
        "output_model": Answer,
        "model": "mimo-v2.6-flash",
    }
    return LLMRequest(**{**values, **overrides})


@respx.mock
async def test_sends_a_strict_schema_and_reads_the_answer() -> None:
    route = respx.post(URL).mock(
        return_value=httpx.Response(200, json=completion('{"name": "Ada", "years": 9}'))
    )

    result = await provider().generate(request())

    assert result.output == Answer(name="Ada", years=9)
    assert (result.provider, result.model) == (ProviderName.mimo, "mimo-v2.6-flash")
    # Reasoning is part of completion_tokens, billed as output.
    assert (result.input_tokens, result.output_tokens) == (2400, 3700)
    sent = route.calls[0].request
    assert sent.headers["Authorization"] == "Bearer sk-mimo-test"
    body = json.loads(sent.content)
    assert body["model"] == "mimo-v2.6-flash"
    assert body["messages"] == [
        {"role": "system", "content": "You extract."},
        {"role": "user", "content": "Extract this."},
    ]
    assert body["response_format"] == {
        "type": "json_schema",
        "json_schema": {"name": "Answer", "strict": True, "schema": llm_schema(Answer)},
    }
    assert "thinking" not in body


@respx.mock
async def test_pdfs_are_sent_as_page_images() -> None:
    route = respx.post(URL).mock(
        return_value=httpx.Response(200, json=completion('{"name": "Ada", "years": 9}'))
    )

    await provider().generate(request(document=SAMPLE_PDF))

    [message] = [
        m for m in json.loads(route.calls[0].request.content)["messages"] if m["role"] == "user"
    ]
    image, text = message["content"]
    assert image["type"] == "image_url"
    prefix = "data:image/png;base64,"
    assert image["image_url"]["url"].startswith(prefix)
    assert base64.b64decode(image["image_url"]["url"][len(prefix) :]).startswith(PNG)
    assert text == {"type": "text", "text": "Extract this."}


@respx.mock
async def test_busy_and_dropped_responses_are_retried_once() -> None:
    route = respx.post(URL).mock(
        side_effect=[
            httpx.Response(503, json={"error": {"type": "ServiceUnavailableError"}}),
            httpx.Response(200, json=completion('{"name": "Ada", "years": 9}')),
        ]
    )

    assert (await provider().generate(request())).output.name == "Ada"
    assert len(route.calls) == 2

    route.side_effect = [
        httpx.RemoteProtocolError("peer closed connection"),
        httpx.Response(200, json=completion('{"name": "Bo", "years": 1}')),
    ]
    assert (await provider().generate(request())).output.name == "Bo"


@pytest.mark.parametrize(
    ("status", "code"),
    [(429, "rate_limited"), (402, "provider_error"), (500, "provider_error")],
)
@respx.mock
async def test_http_errors_become_provider_errors(status: int, code: str) -> None:
    error = {"error": {"code": str(status), "message": "Insufficient account balance"}}
    route = respx.post(URL).mock(return_value=httpx.Response(status, json=error))

    with pytest.raises(ProviderError) as raised:
        await provider().generate(request())

    assert raised.value.details == {
        "provider": "mimo",
        "error_code": code,
        "provider_status": status,
    }
    # 429 and 5xx are retried once; 402 is not.
    assert len(route.calls) == (1 if status == 402 else 2)


@respx.mock
async def test_errors_without_a_json_body_still_report_the_status() -> None:
    respx.post(URL).mock(return_value=httpx.Response(400, text="Bad gateway page"))

    with pytest.raises(ProviderError) as raised:
        await provider().generate(request())

    assert raised.value.details["provider_status"] == 400


@respx.mock
async def test_repeated_connection_failures_are_provider_errors() -> None:
    respx.post(URL).mock(side_effect=httpx.ConnectError("down"))

    with pytest.raises(ProviderError):
        await provider().generate(request())


@pytest.mark.parametrize(
    ("reply", "code"),
    [
        (completion('{"name": "Ada"', finish_reason="length"), "output_too_long"),
        (completion("", finish_reason="content_filter"), "refused"),
        (completion('{"name": "Ada"}'), "invalid_output"),
    ],
)
@respx.mock
async def test_unfinished_answers_are_provider_errors(reply: dict[str, Any], code: str) -> None:
    respx.post(URL).mock(return_value=httpx.Response(200, json=reply))

    with pytest.raises(ProviderError) as raised:
        await provider().generate(request())

    assert raised.value.details["error_code"] == code


@respx.mock
async def test_timeouts_become_provider_timeouts() -> None:
    respx.post(URL).mock(side_effect=httpx.ReadTimeout("slow"))

    with pytest.raises(ProviderTimeout) as raised:
        await provider().generate(request())

    assert raised.value.details == {"provider": "mimo", "error_code": "timeout"}


def test_pdf_pages_render_as_png() -> None:
    [page] = pdf_to_pngs(SAMPLE_PDF)

    assert page.startswith(PNG)


def test_only_the_first_pages_are_rendered() -> None:
    assert pdf_to_pngs(SAMPLE_PDF, max_pages=0) == []


def test_broken_pdfs_are_explained() -> None:
    with pytest.raises(ValidationFailed, match="This PDF could not be read"):
        pdf_to_pngs(b"%PDF-1.7 truncated")
