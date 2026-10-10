"""Renderer service: POST /render, GET /healthz, GET /templates."""

from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel


class Health(BaseModel):
    status: Literal["ok"] = "ok"


app = FastAPI(title="Vitae renderer", docs_url=None, redoc_url=None)


@app.get("/healthz")
async def healthz() -> Health:
    return Health()
