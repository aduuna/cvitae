"""App factory: routers, middleware, error handlers and the SPA static mount."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.exceptions import HTTPException
from starlette.responses import Response
from starlette.types import Scope

from api.ai.models import model_options
from api.db.base import create_engine, session_factory
from api.errors import install_error_handlers
from api.logs import configure_logging
from api.ports.auth import AuthVerifier, DevVerifier, FirebaseVerifier
from api.ports.billing import HttpPaystackClient
from api.ports.llm.base import LLMProvider, ProviderName
from api.ports.llm.claude import ClaudeProvider
from api.ports.llm.gemini import GeminiProvider
from api.ports.llm.mimo import MimoProvider
from api.ports.llm.registry import ProviderRegistry
from api.ports.renderer import GoogleIdTokenAuth, HttpRendererClient
from api.ports.storage import GcsStorage, LocalStorage, Storage
from api.routers import (
    billing,
    client_config,
    documents,
    imports,
    jobs,
    me,
    profiles,
    tailor,
    templates,
    uploads,
    webhooks,
)
from api.services.billing import Billing
from api.settings import Settings


class Health(BaseModel):
    status: Literal["ok"] = "ok"


# The SPA shell for client-side routes. index.html is the landing page, prerendered for `/`.
SPA_FALLBACK = "spa.html"


class SpaStaticFiles(StaticFiles):
    """Serves the built SPA; unknown paths get the shell so client-side routes work on reload."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code != 404 or path.startswith("api/"):
                raise
            return await super().get_response(SPA_FALLBACK, scope)


def build_auth_verifier(settings: Settings) -> AuthVerifier:
    if settings.auth_mode == "dev":
        return DevVerifier()
    if settings.firebase_project_id is None:  # pragma: no cover - Settings requires it
        raise RuntimeError("AUTH_MODE=firebase needs FIREBASE_PROJECT_ID")
    return FirebaseVerifier(settings.firebase_project_id)


def build_storage(settings: Settings) -> Storage:
    if settings.storage_mode == "gcs" and settings.gcs_bucket:
        return GcsStorage(settings.gcs_bucket)
    return LocalStorage(settings.local_storage_dir)


def build_renderer(settings: Settings) -> HttpRendererClient:
    auth = GoogleIdTokenAuth(settings.renderer_url) if settings.renderer_auth == "oidc" else None
    return HttpRendererClient(settings.renderer_url, auth=auth)


def build_providers(settings: Settings) -> ProviderRegistry:
    """Each provider whose key is set, and the AI models they offer."""
    providers: dict[ProviderName, LLMProvider] = {}
    if settings.anthropic_api_key:
        providers[ProviderName.claude] = ClaudeProvider(
            settings.anthropic_api_key.get_secret_value(),
            settings.llm_timeout_seconds,
            fallback_models=frozenset({settings.claude_model_large}),
        )
    if settings.gemini_api_key:
        providers[ProviderName.gemini] = GeminiProvider(
            settings.gemini_api_key.get_secret_value(), settings.llm_timeout_seconds
        )
    if settings.mimo_api_key:
        providers[ProviderName.mimo] = MimoProvider(
            settings.mimo_api_key.get_secret_value(), settings.mimo_timeout_seconds
        )
    return ProviderRegistry(providers, model_options(settings))


def build_billing(settings: Settings) -> Billing | None:
    """Paystack and the Pro plan, when all billing settings are present."""
    key, plan, callback = (
        settings.paystack_secret_key,
        settings.paystack_pro_plan_code,
        settings.paystack_callback_url,
    )
    if not (key and plan and callback):
        return None
    return Billing(HttpPaystackClient(key.get_secret_value()), plan, callback)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    engine = create_engine(settings.database_url)
    renderer = build_renderer(settings)
    billing_setup = build_billing(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
        yield
        await renderer.aclose()
        if billing_setup and isinstance(billing_setup.client, HttpPaystackClient):
            await billing_setup.client.aclose()
        await engine.dispose()

    app = FastAPI(
        title="Chameleon vitae API",
        openapi_url="/api/openapi.json",
        docs_url="/api/docs",
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.sessions = session_factory(engine)
    app.state.auth_verifier = build_auth_verifier(settings)
    app.state.renderer = renderer
    app.state.storage = build_storage(settings)
    app.state.providers = build_providers(settings)
    app.state.billing = billing_setup
    install_error_handlers(app)

    v1 = APIRouter(prefix="/api/v1")

    @v1.get("/healthz", tags=["health"])
    async def healthz() -> Health:
        return Health()

    for module in (
        client_config,
        me,
        profiles,
        documents,
        templates,
        uploads,
        imports,
        jobs,
        tailor,
        billing,
        webhooks,
    ):
        v1.include_router(module.router)
    app.include_router(v1)

    if settings.static_dir:
        app.mount("/", SpaStaticFiles(directory=Path(settings.static_dir), html=True), name="spa")
    return app


app = create_app()
if app.state.settings.env in ("dev", "prod"):
    # Deployed: structured logs for Cloud Logging. Locally and in tests, plain logs.
    configure_logging()
