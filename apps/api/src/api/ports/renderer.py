"""The renderer port: compiles CV data with a template into SVG pages or a PDF."""

import asyncio
import json
import time
from collections.abc import AsyncGenerator, Callable
from typing import Any, Protocol

import httpx
from google.auth import jwt
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token
from pydantic import TypeAdapter, ValidationError

from api.errors import RenderFailed, ServiceUnavailable
from cvcore.rendering import (
    OutputFormat,
    Paper,
    RenderError,
    RenderRequest,
    SvgPages,
    TemplateMeta,
)

_templates_adapter = TypeAdapter(list[TemplateMeta])

TEMPLATES_TTL_SECONDS = 300

# Refresh an ID token this long before it expires.
TOKEN_REFRESH_MARGIN_SECONDS = 300

type TokenFetcher = Callable[[str], str]


def fetch_google_id_token(audience: str) -> str:
    """An ID token for `audience` from the metadata server (Cloud Run) or local credentials."""
    return id_token.fetch_id_token(GoogleRequest(), audience)


class GoogleIdTokenAuth(httpx.Auth):
    """Adds `Authorization: Bearer <Google ID token>` for the renderer's URL, so Cloud Run IAM
    lets the call through. Tokens are cached until shortly before they expire."""

    def __init__(self, audience: str, fetch: TokenFetcher = fetch_google_id_token) -> None:
        self._audience = audience
        self._fetch = fetch
        self._token: tuple[str, float] | None = None
        self._lock = asyncio.Lock()

    async def _current(self) -> str:
        async with self._lock:
            if self._token is None or self._token[1] - time.time() < TOKEN_REFRESH_MARGIN_SECONDS:
                token = await asyncio.to_thread(self._fetch, self._audience)
                claims = jwt.decode(token, verify=False)
                self._token = (token, float(claims["exp"]))
            return self._token[0]

    async def async_auth_flow(
        self, request: httpx.Request
    ) -> AsyncGenerator[httpx.Request, httpx.Response]:
        try:
            token = await self._current()
        except Exception as exc:
            raise ServiceUnavailable("The renderer could not be authorised. Try again.") from exc
        request.headers["Authorization"] = f"Bearer {token}"
        yield request


class RendererClient(Protocol):
    async def render_svg(
        self, template_id: str, data: dict[str, Any], paper: Paper, *, source_links: bool = False
    ) -> SvgPages:
        """`source_links`: link each part to its form field, for click-to-edit previews."""
        ...

    async def render_pdf(self, template_id: str, data: dict[str, Any], paper: Paper) -> bytes: ...

    async def templates(self) -> list[TemplateMeta]: ...


class HttpRendererClient:
    """Calls the renderer service. 422 becomes RenderFailed with diagnostics; a busy renderer
    (429 or 503) gets one retry. Template metadata is cached for a few minutes."""

    def __init__(
        self,
        base_url: str,
        client: httpx.AsyncClient | None = None,
        auth: httpx.Auth | None = None,
    ) -> None:
        self._client = client or httpx.AsyncClient(base_url=base_url, timeout=30, auth=auth)
        self._templates: tuple[float, list[TemplateMeta]] | None = None

    async def aclose(self) -> None:
        await self._client.aclose()

    async def render_svg(
        self, template_id: str, data: dict[str, Any], paper: Paper, *, source_links: bool = False
    ) -> SvgPages:
        response = await self._render(template_id, data, paper, "svg", source_links)
        return SvgPages.model_validate_json(response.content)

    async def render_pdf(self, template_id: str, data: dict[str, Any], paper: Paper) -> bytes:
        response = await self._render(template_id, data, paper, "pdf")
        return response.content

    async def templates(self) -> list[TemplateMeta]:
        now = time.monotonic()
        if self._templates is None or now - self._templates[0] > TEMPLATES_TTL_SECONDS:
            response = await self._send("GET", "/templates")
            self._templates = (now, _templates_adapter.validate_json(response.content))
        return self._templates[1]

    async def _render(
        self,
        template_id: str,
        data: dict[str, Any],
        paper: Paper,
        format: OutputFormat,
        source_links: bool = False,
    ) -> httpx.Response:
        body = RenderRequest(
            files={"data.json": json.dumps(data)},
            template_id=template_id,
            format=format,
            paper=paper,
            source_links=source_links,
        )
        response = await self._send("POST", "/render", json=body.model_dump())
        if response.status_code == 422:
            try:
                error = RenderError.model_validate_json(response.content)
            except ValidationError:
                error = None
            diagnostics = [d.model_dump() for d in error.diagnostics] if error else []
            raise RenderFailed(
                "The CV could not be rendered.",
                {"code": error.code if error else "compile_error", "diagnostics": diagnostics},
            )
        return response

    async def _send(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        for attempt in range(2):
            try:
                response = await self._client.request(method, url, **kwargs)
            except httpx.TransportError as exc:
                raise ServiceUnavailable("The renderer is not reachable. Try again.") from exc
            if response.status_code not in (429, 503) or attempt == 1:
                break
        if response.status_code in (429, 503):
            raise ServiceUnavailable("The renderer is busy. Try again in a moment.")
        if response.status_code >= 400 and response.status_code != 422:
            raise ServiceUnavailable(f"The renderer failed with status {response.status_code}.")
        return response


# One page per SVG, sized like an A4 page in points; enough for tests and local work without Typst.
_FAKE_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="595.28pt" height="841.89pt" '
    'viewBox="0 0 595.28 841.89"><text x="40" y="60">{name}</text></svg>'
)


class FakeRendererClient:
    """Deterministic renderer for tests: one SVG page per CV, a tiny PDF, two templates."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, Any]]] = []
        self.source_links: list[bool] = []
        """Per SVG render, whether source links were asked for."""
        self.fail_with: RenderFailed | None = None

    async def render_svg(
        self, template_id: str, data: dict[str, Any], paper: Paper, *, source_links: bool = False
    ) -> SvgPages:
        self._record("svg", template_id, data)
        self.source_links.append(source_links)
        name = str(data["basics"]["name"]).replace("<", "")
        return SvgPages(pages=[_FAKE_SVG.format(name=name)], page_count=1)

    async def render_pdf(self, template_id: str, data: dict[str, Any], paper: Paper) -> bytes:
        self._record("pdf", template_id, data)
        return b"%PDF-1.7\n% fake\n"

    async def templates(self) -> list[TemplateMeta]:
        return [
            TemplateMeta(
                id="classic",
                name="Classic",
                description="Serif, centred header, navy section rules.",
                paper_sizes=["a4", "us-letter"],
                target_pages=1,
            ),
            TemplateMeta(
                id="compact",
                name="Compact",
                description="Denser spacing and smaller type for long careers.",
                paper_sizes=["a4", "us-letter"],
                target_pages=1,
            ),
        ]

    def _record(self, format: str, template_id: str, data: dict[str, Any]) -> None:
        if self.fail_with:
            raise self.fail_with
        self.calls.append((format, template_id, data))
