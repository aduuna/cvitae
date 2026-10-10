"""GET /templates and template previews with the default profile or the sample."""

from typing import Any

from httpx import AsyncClient

from api.ports.renderer import FakeRendererClient


async def test_lists_templates(client: AsyncClient) -> None:
    response = await client.get("/api/v1/templates")

    assert [t["id"] for t in response.json()] == ["classic", "compact"]


async def test_preview_uses_the_sample_without_a_profile(
    client: AsyncClient, renderer: FakeRendererClient, sample_content: dict[str, Any]
) -> None:
    response = await client.get("/api/v1/templates/compact/preview")

    assert response.status_code == 200
    assert response.json()["page_count"] == 1
    fmt, template_id, data = renderer.calls[-1]
    assert (fmt, template_id) == ("svg", "compact")
    assert data["basics"]["name"] == sample_content["basics"]["name"]


async def test_preview_uses_the_default_profile(
    client: AsyncClient, renderer: FakeRendererClient, sample_content: dict[str, Any]
) -> None:
    mine = {**sample_content, "basics": {**sample_content["basics"], "name": "Grace Hopper"}}
    await client.post("/api/v1/profiles", json={"name": "Mine", "content": mine})

    await client.get("/api/v1/templates/classic/preview")

    assert renderer.calls[-1][2]["basics"]["name"] == "Grace Hopper"


async def test_preview_skips_an_unnamed_default_profile(
    client: AsyncClient, renderer: FakeRendererClient, sample_content: dict[str, Any]
) -> None:
    await client.post("/api/v1/profiles", json={"name": "Empty"})

    await client.get("/api/v1/templates/classic/preview")

    assert renderer.calls[-1][2]["basics"]["name"] == sample_content["basics"]["name"]


async def test_preview_of_an_unknown_template(client: AsyncClient) -> None:
    response = await client.get("/api/v1/templates/fancy/preview")

    assert response.status_code == 422


async def test_preview_needs_sign_in(make_client: Any) -> None:
    async with make_client(user=None) as anonymous:
        response = await anonymous.get("/api/v1/templates/classic/preview")

    assert response.status_code == 401
