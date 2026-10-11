"""App wiring: settings guard, auth, error envelope, SPA serving, OpenAPI export."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Literal

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from api.export_openapi import main as export_openapi
from api.main import (
    build_auth_verifier,
    build_providers,
    build_renderer,
    build_storage,
    create_app,
)
from api.ports.auth import FirebaseVerifier
from api.ports.renderer import GoogleIdTokenAuth
from api.ports.storage import GcsStorage, LocalStorage
from api.settings import DatabaseSettings, Settings

DB = "postgresql+psycopg://unused"

PLANS = [
    {"id": "free", "label": "Free", "documents": 3, "profiles": 1, "ai_runs": 5},
    {"id": "pro", "label": "Pro", "documents": 100, "profiles": 10, "ai_runs": 150},
]


def firebase_settings(env: Literal["dev", "prod"] = "dev") -> Settings:
    return Settings(
        env=env,
        auth_mode="firebase",
        database_url=DB,
        firebase_project_id="cvitae-test",
        firebase_api_key="key",
        firebase_auth_domain="cvitae-test.firebaseapp.com",
        firebase_app_id="1:2:web:3",
        # Explicit values win over a developer's .env, which may hold real keys.
        anthropic_api_key=None,
        gemini_api_key=None,
        mimo_api_key=None,
    )


@pytest.mark.parametrize("env", ["dev", "prod"])
def test_dev_auth_is_refused_in_deployed_envs(env: Literal["dev", "prod"]) -> None:
    with pytest.raises(ValidationError, match=f"AUTH_MODE=dev is not allowed when ENV={env}"):
        Settings(env=env, auth_mode="dev", database_url=DB)


@pytest.mark.parametrize("env", ["local", "test"])
def test_dev_auth_is_allowed_locally(env: Literal["local", "test"]) -> None:
    assert Settings(env=env, auth_mode="dev", database_url=DB).auth_mode == "dev"


def test_firebase_auth_needs_the_web_config() -> None:
    with pytest.raises(ValidationError, match="FIREBASE_API_KEY, FIREBASE_APP_ID"):
        Settings(
            env="dev",
            auth_mode="firebase",
            database_url=DB,
            firebase_project_id="p",
            firebase_auth_domain="d",
        )


def test_firebase_auth_builds_the_firebase_verifier() -> None:
    assert isinstance(build_auth_verifier(firebase_settings("prod")), FirebaseVerifier)


def test_gcs_storage_needs_a_bucket() -> None:
    with pytest.raises(ValidationError, match="GCS_BUCKET"):
        Settings(env="test", auth_mode="dev", database_url=DB, storage_mode="gcs")


def test_storage_follows_the_mode(tmp_path: Path) -> None:
    local = Settings(env="test", auth_mode="dev", database_url=DB, local_storage_dir=tmp_path)
    gcs = Settings(env="test", auth_mode="dev", database_url=DB, storage_mode="gcs", gcs_bucket="b")

    assert isinstance(build_storage(local), LocalStorage)
    assert isinstance(build_storage(gcs), GcsStorage)


async def test_renderer_auth_follows_the_mode() -> None:
    plain = build_renderer(Settings(env="test", auth_mode="dev", database_url=DB))
    oidc = build_renderer(
        Settings(env="test", auth_mode="dev", database_url=DB, renderer_auth="oidc")
    )

    assert plain._client.auth is None
    assert isinstance(oidc._client.auth, GoogleIdTokenAuth)
    await plain.aclose()
    await oidc.aclose()


async def test_client_config_in_dev_mode(client: AsyncClient) -> None:
    response = await client.get("/api/v1/client-config", headers={"X-Dev-User": ""})

    config = response.json()
    assert (config["auth_mode"], config["firebase"]) == ("dev", None)
    assert [m["id"] for m in config["ai_models"]] == [
        "mimo-flash",
        "claude-haiku",
        "gemini-flash-lite",
        "mimo-pro",
        "gemini-flash",
        "claude-sonnet",
    ]
    assert config["ai_models"][0] == {
        "id": "mimo-flash",
        "label": "MiMo Flash",
        "provider": "mimo",
        "plan": "free",
    }
    assert (config["default_ai_model"], config["plans_enforced"]) == ("mimo-flash", True)
    assert config["plans"] == PLANS
    # No Paystack settings in tests: nobody can upgrade.
    assert config["billing_enabled"] is False


async def test_client_config_with_firebase_needs_no_sign_in() -> None:
    app = create_app(firebase_settings())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        response = await c.get("/api/v1/client-config")

    assert response.json() == {
        "auth_mode": "firebase",
        "firebase": {
            "api_key": "key",
            "auth_domain": "cvitae-test.firebaseapp.com",
            "project_id": "cvitae-test",
            "app_id": "1:2:web:3",
        },
        "ai_models": [],
        "default_ai_model": None,
        "plans_enforced": True,
        "plans": PLANS,
        "billing_enabled": False,
    }


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


async def test_openapi_lists_the_routes(client: AsyncClient) -> None:
    paths = (await client.get("/api/openapi.json")).json()["paths"]

    assert {
        "/api/v1/healthz",
        "/api/v1/client-config",
        "/api/v1/me",
        "/api/v1/templates/{template_id}/preview",
        "/api/v1/imports",
        "/api/v1/uploads",
        "/api/v1/uploads/{upload_id}",
        "/api/v1/jobs",
        "/api/v1/jobs/{job_id}",
        "/api/v1/tailor",
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


def test_providers_need_their_keys() -> None:
    def registry(**keys: str | None) -> list[str]:
        settings = Settings(
            env="test",
            auth_mode="dev",
            database_url=DB,
            anthropic_api_key=keys.get("anthropic"),  # type: ignore[arg-type]
            gemini_api_key=keys.get("gemini"),  # type: ignore[arg-type]
            mimo_api_key=keys.get("mimo"),  # type: ignore[arg-type]
        )
        return [option.id for option in build_providers(settings).options]

    assert registry() == []
    assert registry(anthropic="sk-ant") == ["claude-haiku", "claude-sonnet"]
    assert registry(gemini="g", mimo="m") == [
        "mimo-flash",
        "gemini-flash-lite",
        "mimo-pro",
        "gemini-flash",
    ]


def test_the_default_model_falls_back_to_one_that_is_offered() -> None:
    settings = Settings(
        env="test",
        auth_mode="dev",
        database_url=DB,
        anthropic_api_key="sk-ant",  # type: ignore[arg-type]
        gemini_api_key=None,
        mimo_api_key=None,
    )

    assert build_providers(settings).option(settings.default_ai_model) is None
