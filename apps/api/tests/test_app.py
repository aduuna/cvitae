"""App wiring: settings guard, auth, error envelope, SPA serving, OpenAPI export."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Literal

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from api.export_openapi import main as export_openapi
from api.main import build_auth_verifier, create_app
from api.settings import DatabaseSettings, Settings

DB = "postgresql+psycopg://unused"


@pytest.mark.parametrize("env", ["dev", "prod"])
def test_dev_auth_is_refused_in_deployed_envs(env: Literal["dev", "prod"]) -> None:
    with pytest.raises(ValidationError, match=f"AUTH_MODE=dev is not allowed when ENV={env}"):
        Settings(env=env, auth_mode="dev", database_url=DB)


@pytest.mark.parametrize("env", ["local", "test"])
def test_dev_auth_is_allowed_locally(env: Literal["local", "test"]) -> None:
    assert Settings(env=env, auth_mode="dev", database_url=DB).auth_mode == "dev"


def test_firebase_auth_is_not_available_yet() -> None:
    settings = Settings(env="prod", auth_mode="firebase", database_url=DB)

    with pytest.raises(RuntimeError, match="M2"):
        build_auth_verifier(settings)


def test_migrations_prefer_the_direct_url() -> None:
    assert DatabaseSettings(database_url="pooled").migration_url == "pooled"
    direct = DatabaseSettings(database_url="pooled", database_url_direct="direct")
    assert direct.migration_url == "direct"


async def test_healthz(client: AsyncClient) -> None:
    response = await client.get("/api/v1/healthz")

    assert response.json() == {"status": "ok"}


async def test_requests_need_a_signed_in_user(make_client: Callable[..., AsyncClient]) -> None:
    async with make_client(user=None) as anonymous:
        response = await anonymous.get("/api/v1/profiles")

    assert response.status_code == 401
    assert response.json() == {
        "error": {
            "code": "unauthorized",
            "message": "Sign in to continue. In dev mode, send an X-Dev-User header.",
            "details": {},
        }
    }


async def test_dev_user_emails_are_normalised(make_client: Callable[..., AsyncClient]) -> None:
    async with make_client(user="  Ada@Example.com ") as shouting, make_client() as plain:
        await shouting.post("/api/v1/profiles", json={"name": "Mine"})
        listed = (await plain.get("/api/v1/profiles")).json()

    assert [p["name"] for p in listed] == ["Mine"]


async def test_unknown_routes_use_the_envelope(client: AsyncClient) -> None:
    response = await client.get("/api/v1/nothing-here")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_wrong_methods_use_the_envelope(client: AsyncClient) -> None:
    response = await client.put("/api/v1/profiles")

    assert response.status_code == 405
    assert response.json()["error"]["code"] == "method_not_allowed"


async def test_malformed_ids_are_validation_errors(client: AsyncClient) -> None:
    response = await client.get("/api/v1/profiles/not-a-uuid")

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_failed"
    assert error["details"]["errors"][0]["loc"] == ["path", "profile_id"]


async def test_openapi_lists_the_m1_routes(client: AsyncClient) -> None:
    paths = (await client.get("/api/openapi.json")).json()["paths"]

    assert {
        "/api/v1/healthz",
        "/api/v1/profiles",
        "/api/v1/profiles/{profile_id}",
        "/api/v1/profiles/{profile_id}/duplicate",
        "/api/v1/documents",
        "/api/v1/documents/{document_id}",
        "/api/v1/documents/{document_id}/duplicate",
        "/api/v1/documents/{document_id}/preview",
        "/api/v1/documents/{document_id}/export.pdf",
        "/api/v1/documents/{document_id}/versions",
        "/api/v1/documents/{document_id}/versions/{number}/restore",
        "/api/v1/templates",
    } <= set(paths)


def test_export_openapi_writes_the_schema(tmp_path: Path) -> None:
    target = tmp_path / "openapi.json"

    export_openapi(["export_openapi", str(target)])

    schema = json.loads(target.read_text())
    assert schema["info"]["title"] == "Chameleon vitae API"
    assert "CvContent" in json.dumps(schema["components"]["schemas"])


def test_export_openapi_prints_without_a_path(capsys: pytest.CaptureFixture[str]) -> None:
    export_openapi(["export_openapi"])

    assert json.loads(capsys.readouterr().out)["openapi"].startswith("3.")


async def test_serves_the_spa_with_a_client_route_fallback(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<!doctype html><title>app</title>")
    (tmp_path / "app.js").write_text("console.log(1)")
    settings = Settings(env="test", auth_mode="dev", database_url=DB, static_dir=tmp_path)
    app = create_app(settings)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        index, asset, deep, api = (
            await c.get("/"),
            await c.get("/app.js"),
            await c.get("/app/documents/123"),
            await c.get("/api/v1/missing"),
        )

    assert "<title>app</title>" in index.text
    assert asset.text == "console.log(1)"
    assert "<title>app</title>" in deep.text
    assert api.status_code == 404
    assert api.json()["error"]["code"] == "not_found"
