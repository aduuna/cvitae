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

from api.db.base import create_engine, session_factory
from api.errors import install_error_handlers
from api.ports.auth import AuthVerifier, DevVerifier
from api.ports.renderer import HttpRendererClient
from api.routers import documents, profiles, templates
from api.settings import Settings


class Health(BaseModel):
    status: Literal["ok"] = "ok"


class SpaStaticFiles(StaticFiles):
    """Serves the built SPA; unknown paths get index.html so client-side routes work on reload."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code != 404 or path.startswith("api/"):
                raise
            return await super().get_response("index.html", scope)


def build_auth_verifier(settings: Settings) -> AuthVerifier:
    if settings.auth_mode == "dev":
        return DevVerifier()
    raise RuntimeError("AUTH_MODE=firebase arrives with Firebase sign-in (M2). Use AUTH_MODE=dev.")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    engine = create_engine(settings.database_url)
    renderer = HttpRendererClient(settings.renderer_url)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
        yield
        await renderer.aclose()
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
    install_error_handlers(app)

    v1 = APIRouter(prefix="/api/v1")

    @v1.get("/healthz", tags=["health"])
    async def healthz() -> Health:
        return Health()

    for module in (profiles, documents, templates):
        v1.include_router(module.router)
    app.include_router(v1)

    if settings.static_dir:
        app.mount("/", SpaStaticFiles(directory=Path(settings.static_dir), html=True), name="spa")
    return app


app = create_app()
