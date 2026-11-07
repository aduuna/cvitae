"""Security headers on every response the api sends: the API and the built SPA
(docs/INFRA.md, Security checklist).

The Content Security Policy is as strict as the SPA allows:

- Scripts run only from this origin, plus the inline script SvelteKit puts in each page to start
  the app, which is allowed by its hash (read from the built pages at startup, so a new build
  needs no change here). `theme.js` is a file for the same reason.
- Styles may be inline: Svelte's `style:` bindings, the `display: contents` wrapper in
  `app.html` and CodeMirror's injected style sheets all need it.
- Images may be `data:` and `blob:` URLs: CV previews are SVG pages in `<img src="data:...">`.
- Firebase sign-in (`AUTH_MODE=firebase` only) loads Google's `api.js`, embeds the project's
  `/__/auth/iframe` and talks to the Identity Toolkit and Secure Token APIs.
- The Paystack checkout is a top-level redirect, which no CSP directive restricts. The browser
  extension calls the api from its own pages, where this policy does not apply.
"""

import base64
import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from api.settings import Settings

GOOGLE_API_SCRIPT = "https://apis.google.com"
FIREBASE_CONNECT = (
    "https://identitytoolkit.googleapis.com",
    "https://securetoken.googleapis.com",
)

# FastAPI's Swagger UI loads its script and style from a CDN and starts with an inline script.
DOCS_PATHS = frozenset({"/api/docs", "/api/docs/oauth2-redirect"})
DOCS_CSP = "; ".join(
    [
        "default-src 'none'",
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",
        "img-src 'self' data: https://fastapi.tiangolo.com",
        "connect-src 'self'",
        "base-uri 'none'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ]
)

HSTS = "max-age=31536000; includeSubDomains"
"""One year. Only the api's own host and its subdomains: no `preload`."""

PERMISSIONS_POLICY = "camera=(), microphone=(), geolocation=(), payment=(), usb=()"

# What the HTML spec calls JavaScript MIME types, besides an empty `type` and `module`: a script
# of any other type is data to the browser and is not run.
_JAVASCRIPT_TYPES = frozenset(
    {
        "",
        "module",
        "application/ecmascript",
        "application/javascript",
        "application/x-ecmascript",
        "application/x-javascript",
        "text/ecmascript",
        "text/javascript",
        "text/javascript1.0",
        "text/javascript1.1",
        "text/javascript1.2",
        "text/javascript1.3",
        "text/javascript1.4",
        "text/javascript1.5",
        "text/jscript",
        "text/livescript",
        "text/x-ecmascript",
        "text/x-javascript",
    }
)


class _InlineScripts(HTMLParser):
    """The text of every `<script>` that runs inline: no `src`, and a type the browser runs."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.found: list[str] = []
        self._open: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "script":
            return
        attributes = dict(attrs)
        kind = (attributes.get("type") or "").split(";")[0].strip().lower()
        runs = "src" not in attributes and kind in _JAVASCRIPT_TYPES
        self._open = [] if runs else None

    def handle_data(self, data: str) -> None:
        if self._open is not None:
            self._open.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._open is not None:
            self.found.append("".join(self._open))
            self._open = None


def inline_script_hashes(static_dir: Path) -> list[str]:
    """CSP hash sources for every inline script in the built pages, sorted. The scripts that
    start the SPA differ a little from page to page, so each page's own is allowed."""
    hashes: set[str] = set()
    for page in static_dir.rglob("*.html"):
        parser = _InlineScripts()
        # Reading as text turns CRLF into LF, which is the text the browser hashes.
        parser.feed(page.read_text(encoding="utf-8"))
        parser.close()
        for text in parser.found:
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            hashes.add(f"'sha256-{base64.b64encode(digest).decode()}'")
    return sorted(hashes)


def content_security_policy(settings: Settings, script_hashes: list[str] | None = None) -> str:
    """The policy for the SPA and the API's own responses."""
    firebase = settings.auth_mode == "firebase"
    scripts = ["'self'", *(script_hashes or []), *([GOOGLE_API_SCRIPT] if firebase else [])]
    connect = ["'self'", *(FIREBASE_CONNECT if firebase else ())]
    directives = {
        "default-src": ["'self'"],
        "script-src": scripts,
        "style-src": ["'self'", "'unsafe-inline'"],
        "img-src": ["'self'", "data:", "blob:"],
        "font-src": ["'self'"],
        "connect-src": connect,
        "base-uri": ["'self'"],
        "form-action": ["'self'"],
        "object-src": ["'none'"],
        "frame-ancestors": ["'none'"],
    }
    if firebase and settings.firebase_auth_domain:
        directives["frame-src"] = [f"https://{settings.firebase_auth_domain}"]
    return "; ".join(f"{name} {' '.join(sources)}" for name, sources in directives.items())


@dataclass(frozen=True)
class SecurityHeaders:
    csp: str
    headers: Mapping[str, str]

    def apply(self, headers: MutableHeaders, path: str) -> None:
        """Set the security headers on a response for `path`."""
        for name, value in self.headers.items():
            headers[name] = value
        headers["Content-Security-Policy"] = DOCS_CSP if path in DOCS_PATHS else self.csp

    @classmethod
    def for_settings(cls, settings: Settings) -> "SecurityHeaders":
        hashes = inline_script_hashes(settings.static_dir) if settings.static_dir else []
        return cls(
            csp=content_security_policy(settings, hashes),
            headers={
                "Strict-Transport-Security": HSTS,
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "strict-origin-when-cross-origin",
                "X-Frame-Options": "DENY",
                "Permissions-Policy": PERMISSIONS_POLICY,
            },
        )


class SecurityHeadersMiddleware:
    """Adds the security headers to every HTTP response sent from inside the app: a route, the
    SPA's static files or an error handler. Starlette answers an unhandled exception from outside
    every middleware, so `errors.py`'s handler for it applies the headers itself."""

    def __init__(self, app: ASGIApp, security: SecurityHeaders) -> None:
        self.app = app
        self.security = security

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope["path"]

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                self.security.apply(MutableHeaders(scope=message), path)
            await send(message)

        await self.app(scope, receive, send_with_headers)
