import json
from collections.abc import Callable

import httpx
import pytest

from api.errors import RenderFailed, ServiceUnavailable
from api.ports.renderer import HttpRendererClient

DATA = {"basics": {"name": "Ada"}, "summary": [], "sections": []}
TEMPLATES = [
    {
        "id": "classic",
        "name": "Classic",
        "description": "d",
        "paper_sizes": ["a4"],
        "target_pages": 1,
    }
]


def client_for(handler: Callable[[httpx.Request], httpx.Response]) -> HttpRendererClient:
    transport = httpx.MockTransport(handler)
    return HttpRendererClient(
        "http://renderer.test",
        client=httpx.AsyncClient(transport=transport, base_url="http://renderer.test"),
    )


async def test_svg_request_shape_and_result() -> None:
    seen: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={"pages": ["<svg/>"], "page_count": 1})

    pages = await client_for(handler).render_svg("classic", DATA, "a4")

    assert pages.page_count == 1
    assert seen == [
        {
            "files": {"data.json": json.dumps(DATA)},
            "template_id": "classic",
            "format": "svg",
            "paper": "a4",
        }
    ]


async def test_pdf_bytes() -> None:
    client = client_for(lambda _: httpx.Response(200, content=b"%PDF-1.7"))

    assert await client.render_pdf("classic", DATA, "us-letter") == b"%PDF-1.7"


async def test_compile_errors_become_render_failed() -> None:
    body = {"code": "timeout", "diagnostics": [{"message": "Too slow"}]}
    client = client_for(lambda _: httpx.Response(422, json=body))

    with pytest.raises(RenderFailed) as raised:
        await client.render_svg("classic", DATA, "a4")

    assert raised.value.details == {
        "code": "timeout",
        "diagnostics": [{"message": "Too slow", "line": None, "column": None, "file": None}],
    }


async def test_unexpected_422_bodies_still_fail_cleanly() -> None:
    client = client_for(lambda _: httpx.Response(422, json={"detail": "nope"}))

    with pytest.raises(RenderFailed) as raised:
        await client.render_svg("classic", DATA, "a4")

    assert raised.value.details == {"code": "compile_error", "diagnostics": []}


async def test_a_busy_renderer_gets_one_retry() -> None:
    responses = iter(
        [httpx.Response(503), httpx.Response(200, json={"pages": [], "page_count": 0})]
    )
    client = client_for(lambda _: next(responses))

    assert (await client.render_svg("classic", DATA, "a4")).page_count == 0


async def test_still_busy_after_the_retry() -> None:
    client = client_for(lambda _: httpx.Response(429))

    with pytest.raises(ServiceUnavailable, match="busy"):
        await client.render_svg("classic", DATA, "a4")


async def test_server_errors_and_unreachable_renderer() -> None:
    def unreachable(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(ServiceUnavailable, match="status 500"):
        await client_for(lambda _: httpx.Response(500)).render_pdf("classic", DATA, "a4")
    with pytest.raises(ServiceUnavailable, match="not reachable"):
        await client_for(unreachable).render_pdf("classic", DATA, "a4")


async def test_templates_are_cached() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(200, json=TEMPLATES)

    client = client_for(handler)
    first = await client.templates()
    second = await client.templates()

    assert [t.id for t in first] == ["classic"]
    assert second == first
    assert calls == ["/templates"]
    await client.aclose()
