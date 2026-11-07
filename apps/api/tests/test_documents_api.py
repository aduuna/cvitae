import uuid
from typing import Any

from httpx import AsyncClient

from api.errors import RenderFailed
from api.ports.renderer import FakeRendererClient


async def profile(client: AsyncClient, content: dict[str, Any], name: str = "Data") -> str:
    response = await client.post("/api/v1/profiles", json={"name": name, "content": content})
    assert response.status_code == 201
    return response.json()["id"]


async def document(client: AsyncClient, profile_id: str, **body: Any) -> dict[str, Any]:
    response = await client.post("/api/v1/documents", json={"profile_id": profile_id, **body})
    assert response.status_code == 201, response.text
    return response.json()


async def test_create_from_a_profile(client: AsyncClient, sample_content: dict[str, Any]) -> None:
    profile_id = await profile(client, sample_content)

    doc = await document(client, profile_id)

    assert doc["name"] == "Data CV"
    assert doc["template_id"] == "classic"
    assert (doc["custom_layout"], doc["layout"]) == (False, None)
    assert doc["profile_id"] == profile_id
    assert doc["job_id"] is None
    assert doc["page_count"] is None
    assert doc["content"]["basics"]["name"] == "Ama Owusu-Mensah"


async def test_a_cv_is_a_snapshot_of_its_profile(
    client: AsyncClient, sample_content: dict[str, Any]
) -> None:
    profile_id = await profile(client, sample_content)
    doc = await document(client, profile_id, name="Bank CV", template_id="compact")
    sample_content["basics"]["name"] = "Changed later"
    await client.patch(f"/api/v1/profiles/{profile_id}", json={"content": sample_content})

    fetched = (await client.get(f"/api/v1/documents/{doc['id']}")).json()

    assert fetched["name"] == "Bank CV"
    assert fetched["template_id"] == "compact"
    assert fetched["content"]["basics"]["name"] == "Ama Owusu-Mensah"


async def test_three_cvs_from_one_profile(
    client: AsyncClient, sample_content: dict[str, Any]
) -> None:
    profile_id = await profile(client, sample_content)
    for name in ["One", "Two", "Three"]:
        await document(client, profile_id, name=name)

    listed = (await client.get("/api/v1/documents")).json()

    assert [d["name"] for d in listed] == ["Three", "Two", "One"]
    assert "content" not in listed[0]


async def test_create_rejects_unknown_templates_and_profiles(
    client: AsyncClient, sample_content: dict[str, Any]
) -> None:
    profile_id = await profile(client, sample_content)

    bad_template = await client.post(
        "/api/v1/documents", json={"profile_id": profile_id, "template_id": "fancy"}
    )
    bad_profile = await client.post("/api/v1/documents", json={"profile_id": str(uuid.uuid4())})

    assert bad_template.status_code == 422
    assert bad_template.json()["error"]["message"] == "There is no template called fancy."
    assert bad_profile.status_code == 404


async def test_rename_switch_template_and_edit(
    client: AsyncClient, sample_content: dict[str, Any]
) -> None:
    doc = await document(client, await profile(client, sample_content))
    content = doc["content"]
    content["summary"] = "Edited"

    response = await client.patch(
        f"/api/v1/documents/{doc['id']}",
        json={"name": "Renamed", "template_id": "compact", "content": content},
    )

    assert response.status_code == 200
    updated = response.json()
    assert (updated["name"], updated["template_id"]) == ("Renamed", "compact")
    assert updated["content"]["summary"] == "Edited"
    assert updated["content"]["sections"] == doc["content"]["sections"]


async def test_switch_to_unknown_template(
    client: AsyncClient, sample_content: dict[str, Any]
) -> None:
    doc = await document(client, await profile(client, sample_content))

    response = await client.patch(f"/api/v1/documents/{doc['id']}", json={"template_id": "x"})

    assert response.status_code == 422


LAYOUT = '#import "/_lib/cv.typ": *\n#let cv = json("data.json")\n= #cv.basics.name\n'


async def test_set_keep_and_remove_a_custom_layout(
    client: AsyncClient, sample_content: dict[str, Any]
) -> None:
    doc = await document(client, await profile(client, sample_content))
    base = f"/api/v1/documents/{doc['id']}"

    set_layout = (await client.patch(base, json={"layout": LAYOUT})).json()
    content = set_layout["content"] | {"summary": "Edited in the form"}
    kept = (await client.patch(base, json={"name": "Typst CV", "content": content})).json()
    listed = (await client.get("/api/v1/documents")).json()
    removed = (await client.patch(base, json={"layout": None})).json()

    assert (set_layout["custom_layout"], set_layout["layout"]) == (True, LAYOUT)
    assert (kept["layout"], kept["content"]["summary"]) == (LAYOUT, "Edited in the form")
    assert listed[0]["custom_layout"] is True
    assert "layout" not in listed[0]
    assert (removed["custom_layout"], removed["layout"]) == (False, None)
    assert removed["content"]["summary"] == "Edited in the form"


async def test_switching_template_drops_the_custom_layout(
    client: AsyncClient, sample_content: dict[str, Any]
) -> None:
    doc = await document(client, await profile(client, sample_content))
    base = f"/api/v1/documents/{doc['id']}"
    await client.patch(base, json={"layout": LAYOUT})

    same = (await client.patch(base, json={"template_id": "classic"})).json()
    switched = (await client.patch(base, json={"template_id": "compact"})).json()
    both = (await client.patch(base, json={"template_id": "classic", "layout": "x"})).json()

    assert same["layout"] == LAYOUT
    assert (switched["template_id"], switched["layout"]) == ("compact", None)
    assert (both["template_id"], both["layout"]) == ("classic", "x")


async def test_layouts_have_a_size_limit(
    client: AsyncClient, sample_content: dict[str, Any]
) -> None:
    doc = await document(client, await profile(client, sample_content))

    response = await client.patch(f"/api/v1/documents/{doc['id']}", json={"layout": "x" * 100_001})

    assert response.status_code == 422


async def test_preview_and_export_use_the_custom_layout(
    client: AsyncClient, sample_content: dict[str, Any], renderer: FakeRendererClient
) -> None:
    doc = await document(client, await profile(client, sample_content))
    base = f"/api/v1/documents/{doc['id']}"
    await client.post(f"{base}/preview")
    await client.patch(base, json={"layout": LAYOUT})

    await client.post(f"{base}/preview")
    await client.get(f"{base}/export.pdf?force=true")

    assert renderer.sources == [None, LAYOUT, LAYOUT]
    assert [call[0] for call in renderer.calls] == ["svg", "svg", "pdf"]
    # Click to edit works on a custom layout too.
    assert renderer.source_links == [True, True]


async def test_render_data_is_what_the_layout_reads(
    client: AsyncClient, sample_content: dict[str, Any]
) -> None:
    doc = await document(client, await profile(client, sample_content))

    response = await client.get(f"/api/v1/documents/{doc['id']}/data.json")

    assert response.status_code == 200
    data = response.json()
    assert data["basics"]["name"] == "Ama Owusu-Mensah"
    assert data["summary"][1] == {"t": "9 years", "b": True, "p": False}
    first_bullet = data["sections"][0]["experience"][0]["bullets"][0]
    assert set(first_bullet) == {"id", "spans"}


async def test_duplicate_and_delete(client: AsyncClient, sample_content: dict[str, Any]) -> None:
    doc = await document(client, await profile(client, sample_content), name="Original")

    copy = (await client.post(f"/api/v1/documents/{doc['id']}/duplicate")).json()
    deleted = await client.delete(f"/api/v1/documents/{doc['id']}")

    assert copy["name"] == "Original (copy)"
    assert copy["content"] == doc["content"]
    assert copy["layout"] is None
    assert deleted.status_code == 204
    assert [d["name"] for d in (await client.get("/api/v1/documents")).json()] == [
        "Original (copy)"
    ]
    assert (await client.delete(f"/api/v1/documents/{doc['id']}")).status_code == 404


async def test_deleting_the_profile_keeps_its_cvs(
    client: AsyncClient, sample_content: dict[str, Any]
) -> None:
    profile_id = await profile(client, sample_content)
    doc = await document(client, profile_id)

    await client.delete(f"/api/v1/profiles/{profile_id}")

    fetched = (await client.get(f"/api/v1/documents/{doc['id']}")).json()
    assert fetched["profile_id"] is None
    assert fetched["content"] == doc["content"]


async def test_preview_renders_saved_content_and_stores_page_count(
    client: AsyncClient, sample_content: dict[str, Any], renderer: FakeRendererClient
) -> None:
    doc = await document(client, await profile(client, sample_content), template_id="compact")

    response = await client.post(f"/api/v1/documents/{doc['id']}/preview")

    assert response.status_code == 200
    body = response.json()
    assert body["page_count"] == 1
    assert body["pages"][0].startswith("<svg")
    fmt, template_id, data = renderer.calls[-1]
    assert (fmt, template_id) == ("svg", "compact")
    assert data["summary"][1] == {"t": "9 years", "b": True, "p": False}
    # The editor's preview links each part to its form field, for click-to-edit.
    assert renderer.source_links == [True]
    listed = (await client.get("/api/v1/documents")).json()
    assert listed[0]["page_count"] == 1


async def test_preview_returns_typst_diagnostics(
    client: AsyncClient, sample_content: dict[str, Any], renderer: FakeRendererClient
) -> None:
    doc = await document(client, await profile(client, sample_content))
    diagnostics = [{"message": "unknown variable: x", "line": 3, "column": 1, "file": "main.typ"}]
    renderer.fail_with = RenderFailed(
        "The CV could not be rendered.", {"code": "compile_error", "diagnostics": diagnostics}
    )

    response = await client.post(f"/api/v1/documents/{doc['id']}/preview")

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "render_failed"
    assert error["details"]["diagnostics"] == diagnostics


async def test_export_is_blocked_while_placeholders_remain(
    client: AsyncClient, sample_content: dict[str, Any]
) -> None:
    doc = await document(client, await profile(client, sample_content))

    response = await client.get(f"/api/v1/documents/{doc['id']}/export.pdf")

    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "conflict"
    assert error["message"] == "This CV still has 1 placeholder. Fill them in, or export anyway."
    assert error["details"]["placeholders"] == [
        {"text": "number of analysts", "bullet_id": "b-hb-2"}
    ]


async def test_export_anyway(client: AsyncClient, sample_content: dict[str, Any]) -> None:
    doc = await document(client, await profile(client, sample_content))

    response = await client.get(f"/api/v1/documents/{doc['id']}/export.pdf?force=true")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")
    assert response.headers["content-disposition"] == (
        "attachment; filename=\"Ama-Owusu-Mensah-CV.pdf\"; filename*=UTF-8''Ama-Owusu-Mensah-CV.pdf"
    )


async def test_export_without_placeholders(
    client: AsyncClient, sample_content: dict[str, Any]
) -> None:
    text = sample_content["sections"][0]["experience"][0]["engagements"][0]["bullets"][1]
    text["text"] = "Built a streaming fraud-signal pipeline on Kafka."
    doc = await document(client, await profile(client, sample_content))

    response = await client.get(f"/api/v1/documents/{doc['id']}/export.pdf")

    assert response.status_code == 200


async def test_save_and_list_versions(client: AsyncClient, sample_content: dict[str, Any]) -> None:
    doc = await document(client, await profile(client, sample_content))

    assert (await client.get(f"/api/v1/documents/{doc['id']}/versions")).json() == []
    first = await client.post(f"/api/v1/documents/{doc['id']}/versions")
    second = await client.post(f"/api/v1/documents/{doc['id']}/versions")

    assert first.status_code == 201
    assert first.json()["number"] == 1
    assert first.json()["reason"] == "manual"
    listed = (await client.get(f"/api/v1/documents/{doc['id']}/versions")).json()
    assert [(v["number"], v["reason"]) for v in listed] == [(2, "manual"), (1, "manual")]
    assert second.json()["number"] == 2


async def test_restore_keeps_unsaved_work_as_an_autosave(
    client: AsyncClient, sample_content: dict[str, Any]
) -> None:
    doc = await document(client, await profile(client, sample_content))
    await client.post(f"/api/v1/documents/{doc['id']}/versions")
    edited = doc["content"] | {"summary": "Unsaved edit"}
    await client.patch(f"/api/v1/documents/{doc['id']}", json={"content": edited})

    response = await client.post(f"/api/v1/documents/{doc['id']}/versions/1/restore")

    assert response.status_code == 200
    assert response.json()["content"] == doc["content"]
    listed = (await client.get(f"/api/v1/documents/{doc['id']}/versions")).json()
    assert [(v["number"], v["reason"]) for v in listed] == [
        (3, "restore"),
        (2, "autosave"),
        (1, "manual"),
    ]
    undo = await client.post(f"/api/v1/documents/{doc['id']}/versions/2/restore")
    assert undo.json()["content"]["summary"] == "Unsaved edit"


async def test_restore_without_changes_adds_no_autosave(
    client: AsyncClient, sample_content: dict[str, Any]
) -> None:
    doc = await document(client, await profile(client, sample_content))
    await client.post(f"/api/v1/documents/{doc['id']}/versions")

    await client.post(f"/api/v1/documents/{doc['id']}/versions/1/restore")

    listed = (await client.get(f"/api/v1/documents/{doc['id']}/versions")).json()
    assert [v["reason"] for v in listed] == ["restore", "manual"]


async def test_versions_keep_the_layout(
    client: AsyncClient, sample_content: dict[str, Any]
) -> None:
    doc = await document(client, await profile(client, sample_content))
    base = f"/api/v1/documents/{doc['id']}"
    await client.patch(base, json={"layout": LAYOUT})
    await client.post(f"{base}/versions")
    await client.patch(base, json={"layout": None})

    restored = (await client.post(f"{base}/versions/1/restore")).json()
    copy = (await client.post(f"{base}/duplicate")).json()

    assert restored["layout"] == LAYOUT
    assert copy["layout"] == LAYOUT
    listed = (await client.get(f"{base}/versions")).json()
    # Removing the layout was unsaved work, so the restore kept it as an autosave first.
    assert [v["reason"] for v in listed] == ["restore", "autosave", "manual"]
    undo = (await client.post(f"{base}/versions/2/restore")).json()
    assert undo["layout"] is None


async def test_a_layout_that_is_removed_is_kept_as_a_version_first(
    client: AsyncClient, sample_content: dict[str, Any]
) -> None:
    doc = await document(client, await profile(client, sample_content))
    base = f"/api/v1/documents/{doc['id']}"
    await client.patch(base, json={"layout": LAYOUT})

    switched = (await client.patch(base, json={"template_id": "compact"})).json()

    assert switched["layout"] is None
    listed = (await client.get(f"{base}/versions")).json()
    assert [v["reason"] for v in listed] == ["autosave"]
    restored = (await client.post(f"{base}/versions/1/restore")).json()
    assert (restored["layout"], restored["template_id"]) == (LAYOUT, "compact")

    # Nothing more is kept for a layout the latest version already holds ...
    await client.patch(base, json={"layout": None})
    assert [v["reason"] for v in (await client.get(f"{base}/versions")).json()] == [
        "restore",
        "autosave",
        "autosave",
    ]
    # ... and a reset keeps the layout it removes, like a switch does.
    await client.patch(base, json={"layout": "#let other = 1"})
    await client.patch(base, json={"layout": None})
    newest = (await client.get(f"{base}/versions")).json()[0]
    assert newest["reason"] == "autosave"
    again = (await client.post(f"{base}/versions/{newest['number']}/restore")).json()
    assert again["layout"] == "#let other = 1"


async def test_switching_template_without_a_layout_keeps_no_version(
    client: AsyncClient, sample_content: dict[str, Any]
) -> None:
    doc = await document(client, await profile(client, sample_content))
    base = f"/api/v1/documents/{doc['id']}"

    await client.patch(base, json={"template_id": "compact"})
    await client.patch(base, json={"layout": None})

    assert (await client.get(f"{base}/versions")).json() == []


async def test_restore_unknown_version(client: AsyncClient, sample_content: dict[str, Any]) -> None:
    doc = await document(client, await profile(client, sample_content))

    response = await client.post(f"/api/v1/documents/{doc['id']}/versions/7/restore")

    assert response.status_code == 404
    assert response.json()["error"]["message"] == "Version 7 of this CV does not exist."


async def test_users_cannot_reach_each_others_cvs(
    client: AsyncClient, other_client: AsyncClient, sample_content: dict[str, Any]
) -> None:
    profile_id = await profile(client, sample_content)
    doc = await document(client, profile_id)
    await client.post(f"/api/v1/documents/{doc['id']}/versions")
    base = f"/api/v1/documents/{doc['id']}"

    assert (await other_client.get("/api/v1/documents")).json() == []
    for response in [
        await other_client.get(base),
        await other_client.patch(base, json={"name": "x"}),
        await other_client.delete(base),
        await other_client.post(f"{base}/duplicate"),
        await other_client.post(f"{base}/preview"),
        await other_client.get(f"{base}/data.json"),
        await other_client.get(f"{base}/export.pdf?force=true"),
        await other_client.get(f"{base}/versions"),
        await other_client.post(f"{base}/versions"),
        await other_client.post(f"{base}/versions/1/restore"),
        await other_client.post("/api/v1/documents", json={"profile_id": profile_id}),
    ]:
        assert response.status_code == 404, response.request.url
    assert (await client.get(base)).status_code == 200


async def test_templates_are_listed(client: AsyncClient) -> None:
    response = await client.get("/api/v1/templates")

    assert response.status_code == 200
    assert [t["id"] for t in response.json()] == ["classic", "compact"]
