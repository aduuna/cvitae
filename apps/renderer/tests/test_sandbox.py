"""The renderer's sandbox: time, memory, size and import limits (docs/BACKEND.md, Sandboxing)."""

import sys
import time
from collections.abc import Callable
from typing import Any

import pytest
from httpx import AsyncClient

MakeClient = Callable[..., AsyncClient]

# About 10^12 loop iterations: Typst runs a few million per second, so this would compile for
# days. Typst rejects `while true` statically, which is why nested loops are used.
ENDLESS = "#for a in range(10000) { for b in range(10000) { for c in range(10000) { } } }\n"


async def render(client: AsyncClient, files: dict[str, str], **body: Any) -> tuple[int, Any]:
    response = await client.post("/render", json={"files": files, **body})
    if response.headers["content-type"] == "application/pdf":
        return response.status_code, response.content
    return response.status_code, response.json()


async def test_a_long_compile_is_killed_at_the_cpu_limit(client: AsyncClient) -> None:
    started = time.monotonic()
    status, body = await render(client, {"main.typ": ENDLESS})
    elapsed = time.monotonic() - started

    assert status == 422
    assert body["code"] == "timeout"
    assert "longer than 10 seconds" in body["diagnostics"][0]["message"]
    # Stopped by RLIMIT_CPU at 10 s of CPU time, before the 15 s wall clock.
    assert 9 <= elapsed < 15, elapsed


async def test_the_wall_clock_limit_kills_the_child(make_client: MakeClient) -> None:
    async with make_client(wall_seconds=1) as client:
        started = time.monotonic()
        status, body = await render(client, {"main.typ": ENDLESS})
        elapsed = time.monotonic() - started

    assert status == 422
    assert body["code"] == "timeout"
    assert elapsed < 4, elapsed


@pytest.mark.parametrize(
    "source",
    [
        '#import "@preview/cetz:0.3.4": canvas\n',
        'Text\n#include "@local/thing:1.0.0"\n',
        '#let x = { import "@preview/tablex:0.0.8" }\n',
    ],
)
async def test_package_imports_are_rejected_before_compiling(
    client: AsyncClient, source: str
) -> None:
    status, body = await render(client, {"main.typ": source})

    assert status == 422
    assert body["code"] == "forbidden_import"
    diagnostic = body["diagnostics"][0]
    assert diagnostic["message"].startswith("Packages cannot be imported (@")
    assert diagnostic["file"] == "main.typ"
    assert diagnostic["line"] == source.count("\n", 0, source.index("@")) + 1


async def test_computed_package_imports_cannot_download(client: AsyncClient) -> None:
    source = '#let name = "@pre" + "view/cetz:0.3.4"\n#import name: canvas\n'

    started = time.monotonic()
    status, body = await render(client, {"main.typ": source})

    assert status == 422
    assert body["code"] == "compile_error"
    assert "failed to download package" in body["diagnostics"][0]["message"]
    assert time.monotonic() - started < 5


@pytest.mark.parametrize(
    "path", ["../secret.typ", "/../secret.typ", "parts/../../secret.typ", "../../etc/passwd"]
)
async def test_imports_outside_the_root_are_rejected(client: AsyncClient, path: str) -> None:
    status, body = await render(client, {"main.typ": f'#include "{path}"\n'})

    assert status == 422
    assert body["code"] == "forbidden_import"
    assert "inside the project" in body["diagnostics"][0]["message"]


async def test_imports_inside_the_root_are_allowed(client: AsyncClient) -> None:
    files = {
        "main.typ": '#import "parts/a.typ": greeting\n#greeting',
        "parts/a.typ": "#let greeting = [Hi]",
    }

    status, body = await render(client, files)

    assert status == 200, body


@pytest.mark.parametrize(
    "name", ["../evil.typ", "/abs.typ", "_lib/cv.typ", "script.py", "a//b.typ", ".hidden.typ"]
)
async def test_file_names_must_stay_inside_the_project(client: AsyncClient, name: str) -> None:
    status, body = await render(client, {"main.typ": "Hi", name: "x"})

    assert status == 422
    assert body["code"] == "forbidden_import"


async def test_at_most_20_files(client: AsyncClient) -> None:
    files = {"main.typ": "Hi"} | {f"part{i}.typ": "" for i in range(20)}

    status, body = await render(client, files)

    assert status == 422
    assert body == {
        "code": "limit_exceeded",
        "diagnostics": [
            {
                "message": "A CV can have at most 20 files.",
                "line": None,
                "column": None,
                "file": None,
            }
        ],
    }


async def test_source_at_most_256_kb(client: AsyncClient) -> None:
    files = {"main.typ": "Hi", "big.typ": "x" * (256 * 1024)}

    status, body = await render(client, files)

    assert status == 422
    assert body["diagnostics"][0]["message"] == "The CV source is larger than 256 KB."


async def test_data_json_at_most_256_kb(make_client: MakeClient) -> None:
    async with make_client(max_source_bytes=1024 * 1024) as client:
        status, body = await render(
            client, {"data.json": '"' + "x" * (256 * 1024) + '"'}, template_id="classic"
        )

    assert status == 422
    assert body["diagnostics"][0]["message"] == "data.json is larger than 256 KB."


async def test_at_most_10_pages(client: AsyncClient) -> None:
    status, body = await render(client, {"main.typ": "#for i in range(11) { pagebreak() }"})

    assert status == 422
    assert body["code"] == "limit_exceeded"
    assert body["diagnostics"][0]["message"] == "The CV has 12 pages; the limit is 10."


async def test_pdf_size_limit(make_client: MakeClient) -> None:
    async with make_client(max_pdf_bytes=200) as client:
        status, body = await render(client, {"main.typ": "Hello"}, format="pdf")

    assert status == 422
    assert body["code"] == "limit_exceeded"
    assert body["diagnostics"][0]["message"].startswith("The PDF is larger than")


@pytest.mark.skipif(sys.platform != "linux", reason="RLIMIT_AS is only enforced on Linux")
async def test_memory_limit(client: AsyncClient) -> None:
    status, body = await render(client, {"main.typ": "#let big = range(200000000)\n#big.len()"})

    assert status == 422
    assert body["code"] == "limit_exceeded"
