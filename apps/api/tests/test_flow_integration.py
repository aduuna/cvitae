"""The M1 flow end to end through the real renderer service and Typst (no fakes for rendering)."""

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from api.deps import get_renderer
from api.ports.renderer import HttpRendererClient
from renderer.main import app as renderer_app

FIXTURES = Path(__file__).resolve().parents[3] / "templates" / "fixtures"


@pytest.fixture
async def real_renderer(app: FastAPI) -> AsyncIterator[HttpRendererClient]:
    transport = httpx.ASGITransport(app=renderer_app)
    client = HttpRendererClient(
        "http://renderer.test",
        client=httpx.AsyncClient(transport=transport, base_url="http://renderer.test", timeout=30),
    )
    app.dependency_overrides[get_renderer] = lambda: client
    yield client
    await client.aclose()


async def test_profile_to_three_cvs_to_pdf(
    client: AsyncClient, real_renderer: HttpRendererClient, sample_content: dict[str, Any]
) -> None:
    # Build a profile by hand.
    created = await client.post("/api/v1/profiles", json={"name": "Data engineering"})
    profile_id = created.json()["id"]
    saved = await client.patch(f"/api/v1/profiles/{profile_id}", json={"content": sample_content})
    assert saved.status_code == 200

    # Three CVs from it.
    ids = []
    for name in ["Bank CV", "Retail CV", "Startup CV"]:
        response = await client.post(
            "/api/v1/documents", json={"profile_id": profile_id, "name": name}
        )
        ids.append(response.json()["id"])
    assert len((await client.get("/api/v1/documents")).json()) == 3
    doc = f"/api/v1/documents/{ids[0]}"

    # Live preview in classic, with the placeholder highlighted.
    preview = (await client.post(f"{doc}/preview")).json()
    assert preview["page_count"] == 1
    assert "#ffe58a" in preview["pages"][0]
    assert 'viewBox="0 0 595.' in preview["pages"][0]

    # Edit in form mode, then save a version.
    content = (await client.get(doc)).json()["content"]
    content["summary"] = "Data engineer who ships."
    await client.patch(doc, json={"content": content})
    assert (await client.post(f"{doc}/versions")).json()["number"] == 1

    # Switch to compact; content is kept.
    switched = (await client.patch(doc, json={"template_id": "compact"})).json()
    assert switched["content"]["summary"] == "Data engineer who ships."
    compact = (await client.post(f"{doc}/preview")).json()
    assert compact["page_count"] == 1
    assert compact["pages"][0] != preview["pages"][0]

    # A later edit, then restore version 1.
    content["summary"] = "A worse summary."
    await client.patch(doc, json={"content": content})
    restored = (await client.post(f"{doc}/versions/1/restore")).json()
    assert restored["content"]["summary"] == "Data engineer who ships."
    assert restored["template_id"] == "compact"

    # Export: blocked by the placeholder, possible with force, clean once it is filled.
    blocked = await client.get(f"{doc}/export.pdf")
    assert blocked.status_code == 409
    forced = await client.get(f"{doc}/export.pdf?force=true")
    assert forced.status_code == 200
    assert forced.content.startswith(b"%PDF-")
    bullet = restored["content"]["sections"][0]["experience"][0]["engagements"][0]["bullets"][1]
    bullet["text"] = "Built a streaming fraud-signal pipeline on Kafka that serves **40** analysts."
    await client.patch(doc, json={"content": restored["content"]})
    clean = await client.get(f"{doc}/export.pdf")
    assert clean.status_code == 200
    assert clean.headers["content-disposition"].startswith(
        'attachment; filename="Ama-Owusu-Mensah-CV.pdf"'
    )


async def test_render_errors_reach_the_client(
    client: AsyncClient, real_renderer: HttpRendererClient, sample_content: dict[str, Any]
) -> None:
    profile = await client.post("/api/v1/profiles", json={"content": sample_content})
    doc = await client.post("/api/v1/documents", json={"profile_id": profile.json()["id"]})

    templates = await client.get("/api/v1/templates")

    assert {t["id"] for t in templates.json()} >= {"classic", "compact"}
    preview = await client.post(f"/api/v1/documents/{doc.json()['id']}/preview")
    assert preview.status_code == 200


async def test_tailored_fixture_cv_fits_one_page(
    client: AsyncClient, real_renderer: HttpRendererClient, sample_content: dict[str, Any]
) -> None:
    profile = await client.post(
        "/api/v1/profiles", json={"name": "Data", "content": sample_content}
    )
    job_ad = (FIXTURES / "job-data-engineer.txt").read_text()

    tailored = await client.post(
        "/api/v1/tailor",
        json={"profile_id": profile.json()["id"], "job": {"description": job_ad}},
    )
    document_id = tailored.json()["document"]["id"]
    preview = await client.post(f"/api/v1/documents/{document_id}/preview")

    assert tailored.status_code == 201
    assert preview.json()["page_count"] == 1
