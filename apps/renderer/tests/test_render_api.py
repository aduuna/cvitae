from collections.abc import Callable

from httpx import AsyncClient

DataJson = Callable[..., str]


async def test_renders_a_template_to_svg_pages(client: AsyncClient, data_json: DataJson) -> None:
    response = await client.post(
        "/render", json={"template_id": "classic", "files": {"data.json": data_json()}}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["page_count"] == len(body["pages"]) == 1
    page = body["pages"][0]
    assert page.startswith("<svg")
    assert 'viewBox="0 0 595.' in page  # A4 by default
    assert "#ffe58a" in page  # the fixture's placeholder is highlighted


async def test_renders_us_letter(client: AsyncClient, data_json: DataJson) -> None:
    response = await client.post(
        "/render",
        json={"template_id": "compact", "files": {"data.json": data_json()}, "paper": "us-letter"},
    )

    assert response.status_code == 200
    assert 'viewBox="0 0 612 792"' in response.json()["pages"][0]


async def test_renders_a_pdf(client: AsyncClient, data_json: DataJson) -> None:
    response = await client.post(
        "/render",
        json={"template_id": "classic", "files": {"data.json": data_json()}, "format": "pdf"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF-")


async def test_renders_an_ejected_project(client: AsyncClient, data_json: DataJson) -> None:
    files = {
        "main.typ": '#import "/_lib/cv.typ": rich\n#let cv = json("data.json")\n#cv.basics.name\n',
        "data.json": data_json(),
    }

    response = await client.post("/render", json={"files": files})

    assert response.status_code == 200
    assert response.json()["page_count"] == 1


async def test_compile_errors_return_diagnostics(client: AsyncClient) -> None:
    files = {"main.typ": "Hello\n#unknown-thing\n"}

    response = await client.post("/render", json={"files": files})

    assert response.status_code == 422
    assert response.json() == {
        "code": "compile_error",
        "diagnostics": [
            {
                "message": "unknown variable: unknown-thing",
                "line": 2,
                "column": 1,
                "file": "main.typ",
            }
        ],
    }


async def test_unknown_template(client: AsyncClient) -> None:
    response = await client.post(
        "/render", json={"template_id": "fancy", "files": {"data.json": "{}"}}
    )

    assert response.status_code == 422
    assert response.json()["diagnostics"][0]["message"] == "There is no template called 'fancy'."


async def test_invalid_requests_use_the_error_shape(client: AsyncClient) -> None:
    response = await client.post("/render", json={"files": {"data.json": "{}"}})

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "compile_error"
    assert "template_id" in body["diagnostics"][0]["message"]


async def test_template_files_cannot_be_replaced(client: AsyncClient) -> None:
    response = await client.post(
        "/render",
        json={"template_id": "classic", "files": {"data.json": "{}", "main.typ": "x"}},
    )

    assert response.status_code == 422


async def test_lists_templates(client: AsyncClient) -> None:
    response = await client.get("/templates")

    assert response.status_code == 200
    templates = {t["id"]: t for t in response.json()}
    assert {"classic", "compact"} <= set(templates)
    assert templates["classic"]["name"] == "Classic"
    assert templates["classic"]["paper_sizes"] == ["a4", "us-letter"]
    assert templates["compact"]["target_pages"] == 1


async def test_healthz(client: AsyncClient) -> None:
    response = await client.get("/healthz")

    assert response.json() == {"status": "ok"}
