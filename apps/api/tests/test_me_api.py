"""GET and PATCH /me, and the default template it sets for new CVs."""

from typing import Any

from httpx import AsyncClient


async def test_me_is_created_on_first_request(client: AsyncClient) -> None:
    me = (await client.get("/api/v1/me")).json()

    assert me["email"] == "ada@example.com"
    assert (me["plan"], me["preferred_ai_model"]) == ("free", None)
    assert (me["display_name"], me["default_template_id"]) == (None, None)


async def test_update_me(client: AsyncClient) -> None:
    response = await client.patch(
        "/api/v1/me",
        json={
            "display_name": "  Ada Lovelace ",
            "preferred_ai_model": "claude-sonnet",
            "default_template_id": "compact",
        },
    )

    assert response.status_code == 200
    me = (await client.get("/api/v1/me")).json()
    assert me["display_name"] == "Ada Lovelace"
    assert me["preferred_ai_model"] == "claude-sonnet"
    assert me["default_template_id"] == "compact"


async def test_partial_updates_keep_other_fields(client: AsyncClient) -> None:
    await client.patch("/api/v1/me", json={"display_name": "Ada"})
    await client.patch("/api/v1/me", json={"preferred_ai_model": "gemini-flash"})

    assert (await client.get("/api/v1/me")).json()["display_name"] == "Ada"


async def test_blank_display_name_clears_it(client: AsyncClient) -> None:
    await client.patch("/api/v1/me", json={"display_name": "Ada"})
    response = await client.patch("/api/v1/me", json={"display_name": "  "})

    assert response.json()["display_name"] is None


async def test_unknown_default_template_is_refused(client: AsyncClient) -> None:
    response = await client.patch("/api/v1/me", json={"default_template_id": "fancy"})

    assert response.status_code == 422
    assert response.json()["error"]["details"] == {"field": "template_id"}


async def test_unknown_provider_is_refused(client: AsyncClient) -> None:
    response = await client.patch("/api/v1/me", json={"preferred_ai_model": "gpt"})

    assert response.status_code == 422


async def test_new_cvs_use_the_default_template(
    client: AsyncClient, sample_content: dict[str, Any]
) -> None:
    profile = await client.post("/api/v1/profiles", json={"name": "P", "content": sample_content})
    await client.patch("/api/v1/me", json={"default_template_id": "compact"})

    default = await client.post("/api/v1/documents", json={"profile_id": profile.json()["id"]})
    chosen = await client.post(
        "/api/v1/documents", json={"profile_id": profile.json()["id"], "template_id": "classic"}
    )

    assert default.json()["template_id"] == "compact"
    assert chosen.json()["template_id"] == "classic"


async def test_users_see_only_themselves(client: AsyncClient, other_client: AsyncClient) -> None:
    await client.patch("/api/v1/me", json={"display_name": "Ada"})

    other = (await other_client.get("/api/v1/me")).json()

    assert (other["email"], other["display_name"]) == ("bob@example.com", None)
