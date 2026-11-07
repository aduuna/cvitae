"""A user's own template reaches the renderer as an ejected CV does: `main.typ` and `data.json` in
`files`, no `template_id`. It compiles against the shared helpers like a built-in template and
runs under the same sandbox (docs/BACKEND.md, Custom templates)."""

import json
from collections.abc import Callable

import pytest
from httpx import AsyncClient

from cvcore.rendering import RenderRequest
from renderer.compile import render
from renderer.previews import fixture_data
from renderer.settings import Settings

SETTINGS = Settings()
FIXTURES = SETTINGS.templates_dir / "fixtures"
USER_TEMPLATE = (FIXTURES / "user-template.typ").read_text()
DataJson = Callable[..., str]


def files(data: str, source: str = USER_TEMPLATE) -> dict[str, str]:
    return {"main.typ": source, "data.json": data}


@pytest.mark.parametrize("fixture", ["profile-sample", "profile-edge", "profile-long"])
async def test_a_user_style_template_renders_every_fixture(fixture: str) -> None:
    data = json.dumps(fixture_data(SETTINGS, fixture))

    output = await render(RenderRequest(files=files(data), format="svg"), SETTINGS)

    assert output.page_count == len(output.svg_pages) >= 1
    assert ("#ffe58a" in "".join(output.svg_pages)) == (
        "[[" in (FIXTURES / f"{fixture}.json").read_text()
    )


async def test_it_fits_one_page_and_follows_the_paper(
    client: AsyncClient, data_json: DataJson
) -> None:
    a4 = await client.post("/render", json={"files": files(data_json())})
    letter = await client.post("/render", json={"files": files(data_json()), "paper": "us-letter"})

    assert a4.status_code == letter.status_code == 200
    assert a4.json()["page_count"] == letter.json()["page_count"] == 1
    assert 'viewBox="0 0 595.' in a4.json()["pages"][0]
    assert 'viewBox="0 0 612 792"' in letter.json()["pages"][0]


async def test_it_makes_a_pdf_and_previews_link_back_to_the_form(
    client: AsyncClient, data_json: DataJson
) -> None:
    pdf = await client.post("/render", json={"files": files(data_json()), "format": "pdf"})
    linked = await client.post("/render", json={"files": files(data_json()), "source_links": True})

    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF-")
    page = linked.json()["pages"][0]
    assert 'href="cv:basics"' in page and 'href="cv:summary"' in page


async def test_the_sandbox_applies_to_a_user_template(
    client: AsyncClient, data_json: DataJson
) -> None:
    package = await client.post(
        "/render",
        json={
            "files": files(data_json(), '#import "@preview/cetz:0.3.4": canvas\n' + USER_TEMPLATE)
        },
    )
    outside = await client.post(
        "/render",
        json={
            "files": files(data_json(), USER_TEMPLATE + '\n#let leak = read("/../../etc/passwd")\n')
        },
    )
    loop = await client.post("/render", json={"files": files(data_json(), "#while true {}\n")})

    assert (package.status_code, package.json()["code"]) == (422, "forbidden_import")
    assert outside.status_code == 422 and outside.json()["code"] == "compile_error"
    assert loop.status_code == 422


async def test_a_user_template_cannot_replace_the_shared_helpers(
    client: AsyncClient, data_json: DataJson
) -> None:
    response = await client.post(
        "/render", json={"files": {**files(data_json()), "_lib/cv.typ": "#let sections() = []"}}
    )

    assert response.status_code == 422 and response.json()["code"] == "forbidden_import"
