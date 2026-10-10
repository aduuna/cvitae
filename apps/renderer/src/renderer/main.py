"""Renderer service: POST /render, GET /healthz, GET /templates."""

from functools import cache
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from cvcore.rendering import Diagnostic, RenderError, RenderRequest, SvgPages, TemplateMeta
from renderer.compile import RenderFailure, render
from renderer.settings import Settings
from renderer.templates import load_templates


class Health(BaseModel):
    status: Literal["ok"] = "ok"


@cache
def get_settings() -> Settings:
    return Settings()


SettingsDep = Annotated[Settings, Depends(get_settings)]

app = FastAPI(title="Chameleon vitae renderer", docs_url=None, redoc_url=None)


@app.exception_handler(RequestValidationError)
async def _invalid_request(_: Request, exc: Exception) -> JSONResponse:
    errors = exc.errors() if isinstance(exc, RequestValidationError) else []
    diagnostics = [
        Diagnostic(message=f"{'.'.join(map(str, e['loc']))}: {e['msg']}") for e in errors
    ]
    error = RenderError(code="compile_error", diagnostics=diagnostics)
    return JSONResponse(error.model_dump(), status_code=422)


@app.get("/healthz")
async def healthz() -> Health:
    return Health()


@app.get("/templates")
async def templates(settings: SettingsDep) -> list[TemplateMeta]:
    return list(load_templates(settings.templates_dir).values())


@app.post(
    "/render",
    response_model=SvgPages,
    responses={
        200: {"content": {"application/pdf": {}}, "description": "SVG pages, or the PDF"},
        422: {"model": RenderError, "description": "Compile error, timeout or limit"},
    },
)
async def render_endpoint(body: RenderRequest, settings: SettingsDep) -> Response:
    try:
        output = await render(body, settings)
    except RenderFailure as failure:
        return JSONResponse(failure.error.model_dump(), status_code=422)
    if output.pdf is not None:
        return Response(output.pdf, media_type="application/pdf")
    return JSONResponse(SvgPages(pages=output.svg_pages, page_count=output.page_count).model_dump())
