"""App factory: routers, middleware, error handlers and the SPA static mount."""

from typing import Literal

from fastapi import APIRouter, FastAPI
from pydantic import BaseModel


class Health(BaseModel):
    status: Literal["ok"] = "ok"


def create_app() -> FastAPI:
    app = FastAPI(
        title="Vitae API",
        openapi_url="/api/openapi.json",
        docs_url="/api/docs",
        redoc_url=None,
    )

    v1 = APIRouter(prefix="/api/v1")

    @v1.get("/healthz", tags=["health"])
    async def healthz() -> Health:
        return Health()

    app.include_router(v1)
    return app


app = create_app()
