"""The renderer port: compiles CV data with a template, or with Typst code sent along (a user's own
template, a CV's custom layout), into SVG pages or a PDF."""

import asyncio
import json
import textwrap
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
    TemplateSource,
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
        self,
        template_id: str,
        data: dict[str, Any],
        paper: Paper,
        *,
        source_links: bool = False,
        source: str | None = None,
    ) -> SvgPages:
        """`source_links`: link each part to its form field, for click-to-edit previews.
        `source`: the main.typ of a user's own template or a CV's custom layout; the renderer
        then ignores `template_id`, which is only a label."""
        ...

    async def render_pdf(
        self, template_id: str, data: dict[str, Any], paper: Paper, *, source: str | None = None
    ) -> bytes: ...

    async def templates(self) -> list[TemplateMeta]: ...

    async def template_source(self, template_id: str) -> TemplateSource:
        """A built-in template's main.typ, where a custom layout starts."""
        ...


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
        self,
        template_id: str,
        data: dict[str, Any],
        paper: Paper,
        *,
        source_links: bool = False,
        source: str | None = None,
    ) -> SvgPages:
        response = await self._render(template_id, data, paper, "svg", source_links, source)
        return SvgPages.model_validate_json(response.content)

    async def render_pdf(
        self, template_id: str, data: dict[str, Any], paper: Paper, *, source: str | None = None
    ) -> bytes:
        response = await self._render(template_id, data, paper, "pdf", source=source)
        return response.content

    async def templates(self) -> list[TemplateMeta]:
        now = time.monotonic()
        if self._templates is None or now - self._templates[0] > TEMPLATES_TTL_SECONDS:
            response = await self._send("GET", "/templates")
            self._templates = (now, _templates_adapter.validate_json(response.content))
        return self._templates[1]

    async def template_source(self, template_id: str) -> TemplateSource:
        response = await self._send("GET", f"/templates/{template_id}/source")
        return TemplateSource.model_validate_json(response.content)

    async def _render(
        self,
        template_id: str,
        data: dict[str, Any],
        paper: Paper,
        format: OutputFormat,
        source_links: bool = False,
        source: str | None = None,
    ) -> httpx.Response:
        # A user's own template or a CV's custom layout travels with the request: the renderer
        # sandboxes it the same way (no packages, no other files, the same limits).
        files = {"data.json": json.dumps(data)}
        if source is not None:
            files["main.typ"] = source
        body = RenderRequest(
            files=files,
            template_id=None if source is not None else template_id,
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


def _strings(value: Any) -> list[str]:
    """Every text in a CV's data.json, in order; ids and section kinds are not text."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [text for item in value for text in _strings(item)]
    if isinstance(value, dict):
        return [
            text
            for key, item in value.items()
            if key not in ("id", "kind")
            for text in _strings(item)
        ]
    return []


def fake_pdf(data: dict[str, Any]) -> bytes:
    """A real one-page PDF whose text layer holds every text of the CV, so code that reads a
    rendered PDF (its text, or an image of its page) works against the fake renderer."""
    lines = textwrap.wrap("  ".join(_strings(data)), 100)
    escaped = [line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") for line in lines]
    text = " ".join(f"({line}) Tj T*" for line in escaped)
    stream = f"BT /F1 6 Tf 7 TL 30 810 Td {text} ET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R "
        "/Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body.encode("cp1252", "replace") + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return out


FAKE_TEMPLATE_SOURCE = '// {id}\n#let cv = json("data.json")\n#cv.basics.name\n'
"""What the fake renderer says a built-in template's main.typ is."""

# What Typst does with `#panic`: the compile fails with the message. The fake does the same, so
# tests can hand it a template that does not compile.
_PANIC = "#panic("


class FakeRendererClient:
    """Deterministic renderer for tests: one SVG page per CV, a one-page PDF holding the CV's
    text, two templates. Typst code sent along (`source`) containing `#panic(` fails to compile."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, Any]]] = []
        self.sources: list[str | None] = []
        """Per render, the Typst code sent along (a user's own template or a custom layout), or
        None for a built-in template."""
        self.source_links: list[bool] = []
        """Per SVG render, whether source links were asked for."""
        self.fail_with: RenderFailed | None = None

    async def render_svg(
        self,
        template_id: str,
        data: dict[str, Any],
        paper: Paper,
        *,
        source_links: bool = False,
        source: str | None = None,
    ) -> SvgPages:
        self._record("svg", template_id, data, source)
        self.source_links.append(source_links)
        name = str(data["basics"]["name"]).replace("<", "")
        return SvgPages(pages=[_FAKE_SVG.format(name=name)], page_count=1)

    async def render_pdf(
        self, template_id: str, data: dict[str, Any], paper: Paper, *, source: str | None = None
    ) -> bytes:
        self._record("pdf", template_id, data, source)
        return fake_pdf(data)

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

    async def template_source(self, template_id: str) -> TemplateSource:
        if template_id not in {template.id for template in await self.templates()}:
            raise ServiceUnavailable("The renderer failed with status 404.")
        return TemplateSource(id=template_id, source=FAKE_TEMPLATE_SOURCE.format(id=template_id))

    def _record(
        self, format: str, template_id: str, data: dict[str, Any], source: str | None
    ) -> None:
        if self.fail_with:
            raise self.fail_with
        if source is not None and _PANIC in source:
            line = source[: source.index(_PANIC)].count("\n") + 1
            raise RenderFailed(
                "The CV could not be rendered.",
                {
                    "code": "compile_error",
                    "diagnostics": [
                        {"message": "panicked with the template's message", "line": line}
                    ],
                },
            )
        self.calls.append((format, template_id, data))
        self.sources.append(source)
