from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from httpx import AsyncClient


@pytest.fixture(autouse=True)
async def pro(make_pro: Callable[[], Awaitable[None]]) -> None:
    """These tests keep several profiles, which takes Pro. Free's limit: test_quotas_api."""
    await make_pro()


async def create(client: AsyncClient, **body: Any) -> dict[str, Any]:
    response = await client.post("/api/v1/profiles", json=body)
    assert response.status_code == 201, response.text
    return response.json()


async def test_list_starts_empty(client: AsyncClient) -> None:
    response = await client.get("/api/v1/profiles")

    assert response.status_code == 200
    assert response.json() == []


async def test_new_profile_has_starter_sections_and_is_default(client: AsyncClient) -> None:
    profile = await create(client)

    assert profile["name"] == "Untitled profile"
    assert profile["is_default"] is True
    content = profile["content"]
    assert content["basics"]["name"] == ""
    assert [(s["kind"], s["title"]) for s in content["sections"]] == [
        ("experience", "Experience"),
        ("education", "Education"),
        ("skills", "Skills"),
    ]
    assert len({s["id"] for s in content["sections"]}) == 3


async def test_second_profile_is_not_default(client: AsyncClient) -> None:
    await create(client, name="Backend")
    second = await create(client, name="Data")

    assert second["is_default"] is False
    listed = (await client.get("/api/v1/profiles")).json()
    assert [p["name"] for p in listed] == ["Data", "Backend"]
    assert "content" not in listed[0]


async def test_create_with_content(client: AsyncClient, sample_content: dict[str, Any]) -> None:
    profile = await create(client, name="Data engineering", content=sample_content)

    fetched = (await client.get(f"/api/v1/profiles/{profile['id']}")).json()
    assert fetched["content"]["basics"]["name"] == "Ama Owusu-Mensah"
    assert fetched["content"] == profile["content"]


async def test_update_name_and_content(client: AsyncClient, sample_content: dict[str, Any]) -> None:
    profile = await create(client)

    response = await client.patch(
        f"/api/v1/profiles/{profile['id']}", json={"name": "Data", "content": sample_content}
    )

    assert response.status_code == 200
    updated = response.json()
    assert updated["name"] == "Data"
    assert updated["content"]["sections"][0]["experience"][0]["org"] == "Northwind Consulting"
    assert updated["updated_at"] >= profile["updated_at"]


async def test_reload_returns_exactly_what_was_saved(
    client: AsyncClient, sample_content: dict[str, Any]
) -> None:
    profile = await create(client)
    sections = sample_content["sections"]
    sample_content["sections"] = [sections[2], sections[0], sections[1], *sections[3:]]
    await client.patch(f"/api/v1/profiles/{profile['id']}", json={"content": sample_content})

    fetched = (await client.get(f"/api/v1/profiles/{profile['id']}")).json()

    assert [s["id"] for s in fetched["content"]["sections"]][:3] == [
        "sec-edu",
        "sec-exp",
        "sec-proj",
    ]


async def test_make_default_moves_the_flag(client: AsyncClient) -> None:
    first = await create(client, name="First")
    second = await create(client, name="Second")

    response = await client.patch(f"/api/v1/profiles/{second['id']}", json={"is_default": True})

    assert response.json()["is_default"] is True
    defaults = {p["name"]: p["is_default"] for p in (await client.get("/api/v1/profiles")).json()}
    assert defaults == {"First": False, "Second": True}
    again = await client.patch(f"/api/v1/profiles/{second['id']}", json={"is_default": True})
    assert again.status_code == 200
    assert first["id"] != second["id"]


async def test_is_default_false_is_rejected(client: AsyncClient) -> None:
    profile = await create(client)

    response = await client.patch(f"/api/v1/profiles/{profile['id']}", json={"is_default": False})

    assert response.status_code == 422


async def test_delete_default_promotes_the_most_recent(client: AsyncClient) -> None:
    first = await create(client, name="First")
    await create(client, name="Second")
    await create(client, name="Third")

    response = await client.delete(f"/api/v1/profiles/{first['id']}")

    assert response.status_code == 204
    defaults = {p["name"]: p["is_default"] for p in (await client.get("/api/v1/profiles")).json()}
    assert defaults == {"Third": True, "Second": False}


async def test_delete_the_last_profile(client: AsyncClient) -> None:
    profile = await create(client)

    assert (await client.delete(f"/api/v1/profiles/{profile['id']}")).status_code == 204
    assert (await client.get("/api/v1/profiles")).json() == []


async def test_duplicate(client: AsyncClient, sample_content: dict[str, Any]) -> None:
    source = await create(client, name="Data", content=sample_content)

    response = await client.post(f"/api/v1/profiles/{source['id']}/duplicate")

    assert response.status_code == 201
    copy = response.json()
    assert copy["name"] == "Data (copy)"
    assert copy["is_default"] is False
    assert copy["content"] == source["content"]
    assert copy["id"] != source["id"]


async def test_unknown_profile_is_not_found(client: AsyncClient) -> None:
    missing = "00000000-0000-4000-8000-000000000000"

    for response in [
        await client.get(f"/api/v1/profiles/{missing}"),
        await client.patch(f"/api/v1/profiles/{missing}", json={"name": "x"}),
        await client.delete(f"/api/v1/profiles/{missing}"),
        await client.post(f"/api/v1/profiles/{missing}/duplicate"),
    ]:
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"


async def test_invalid_content_is_rejected_without_echoing_it(
    client: AsyncClient, sample_content: dict[str, Any]
) -> None:
    profile = await create(client)
    sample_content["basics"]["links"] = [{"label": "Site", "url": "not a url"}]

    response = await client.patch(
        f"/api/v1/profiles/{profile['id']}", json={"content": sample_content}
    )

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_failed"
    assert error["message"].startswith("Check content.basics.links.0.url")
    assert "not a url" not in response.text


async def test_blank_names_are_rejected(client: AsyncClient) -> None:
    response = await client.post("/api/v1/profiles", json={"name": ""})

    assert response.status_code == 422


async def test_users_cannot_see_each_others_profiles(
    client: AsyncClient, other_client: AsyncClient
) -> None:
    profile = await create(client, name="Private")

    assert (await other_client.get("/api/v1/profiles")).json() == []
    assert (await other_client.get(f"/api/v1/profiles/{profile['id']}")).status_code == 404
    patched = await other_client.patch(f"/api/v1/profiles/{profile['id']}", json={"name": "x"})
    assert patched.status_code == 404
    assert (await other_client.delete(f"/api/v1/profiles/{profile['id']}")).status_code == 404
    assert (await client.get(f"/api/v1/profiles/{profile['id']}")).json()["name"] == "Private"


async def test_each_user_has_their_own_default(
    client: AsyncClient, other_client: AsyncClient
) -> None:
    mine = await create(client)
    theirs = await create(other_client)

    assert mine["is_default"] and theirs["is_default"]
