"""Security headers on every response, and a Content Security Policy that fits the SPA."""

import base64
import hashlib
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient, Response
from starlette.types import Message, Receive, Scope, Send

from api.main import create_app
from api.security import (
    DOCS_CSP,
    SecurityHeaders,
    SecurityHeadersMiddleware,
    content_security_policy,
    inline_script_hashes,
)
from api.settings import Settings

DB = "postgresql+psycopg://unused"

# The script SvelteKit puts in every page to start the app, as the build writes it.
BOOTSTRAP = """
				{
					__sveltekit_91w9of = {
						base: "",
						version: "1794033775598"
					};

					const element = document.currentScript.parentElement;

					import("/_app/immutable/entry/start.DDugauHt.js").then(async (kit) => {
						kit.init(__sveltekit_91w9of);
						const app = await import("/_app/immutable/entry/app.Ci4JHav4.js");
						kit.start(app, element);
					});
				}
			"""
SHELL = f"""<!doctype html>
<html lang="en">
	<head>
		<script src="/theme.js"></script>
		<script type="application/ld+json">{{"@type": "WebSite"}}</script>
	</head>
	<body><div style="display: contents"><script>{BOOTSTRAP}</script></div></body>
</html>
"""


def sha256(text: str) -> str:
    return "'sha256-" + base64.b64encode(hashlib.sha256(text.encode()).digest()).decode() + "'"


def directives(policy: str) -> dict[str, list[str]]:
    parsed: dict[str, list[str]] = {}
    for part in policy.split(";"):
        name, *sources = part.split()
        assert name not in parsed, f"{name} is set twice"
        parsed[name] = sources
    return parsed


def settings_for(mode: str = "dev", **more: Any) -> Settings:
    base: dict[str, Any] = {"env": "test", "auth_mode": "dev", "database_url": DB}
    if mode == "firebase":
        base |= {
            "auth_mode": "firebase",
            "firebase_project_id": "cvitae-test",
            "firebase_api_key": "key",
            "firebase_auth_domain": "cvitae-test.firebaseapp.com",
            "firebase_app_id": "1:2:web:3",
        }
    return Settings.model_validate({**base, **more})


@pytest.fixture
def spa(tmp_path: Path) -> Path:
    (tmp_path / "index.html").write_text(SHELL)
    (tmp_path / "spa.html").write_text(SHELL)
    (tmp_path / "app.js").write_text("console.log(1)")
    return tmp_path


async def get(settings: Settings, path: str) -> Response:
    app = create_app(settings)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        return await c.get(path)


# Every response


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/healthz",
        "/api/v1/client-config",
        "/api/v1/profiles",  # 401: an error from a dependency
        "/api/v1/nothing-here",  # 404 from the router
        "/api/openapi.json",
        "/",
        "/app/documents/123",  # the SPA shell for a client-side route
        "/app.js",
    ],
)
async def test_every_response_has_the_security_headers(spa: Path, path: str) -> None:
    response = await get(settings_for(static_dir=spa), path)

    headers = response.headers
    assert headers["strict-transport-security"] == "max-age=31536000; includeSubDomains"
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert headers["x-frame-options"] == "DENY"
    assert headers["permissions-policy"] == (
        "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
    )
    assert "frame-ancestors 'none'" in headers["content-security-policy"]


async def test_a_post_has_them_too() -> None:
    app = create_app(settings_for())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        response = await c.post("/api/v1/webhooks/paystack", content=b"{}")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert "content-security-policy" in response.headers


async def test_each_header_is_sent_once(spa: Path) -> None:
    response = await get(settings_for(static_dir=spa), "/")

    for name in ("content-security-policy", "strict-transport-security", "x-frame-options"):
        assert len(response.headers.get_list(name)) == 1


async def test_non_http_messages_pass_through_untouched() -> None:
    seen: list[Message] = []

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        await send({"type": "websocket.accept"})

    async def send(message: Message) -> None:
        seen.append(message)

    async def receive() -> Message:  # pragma: no cover - never read
        return {"type": "websocket.connect"}

    security = SecurityHeaders.for_settings(settings_for())
    await SecurityHeadersMiddleware(app, security)(
        {"type": "websocket", "path": "/"}, receive, send
    )

    assert seen == [{"type": "websocket.accept"}]


# The policy


def test_the_policy_is_strict_where_the_spa_allows() -> None:
    policy = directives(content_security_policy(settings_for()))

    assert policy["default-src"] == ["'self'"]
    assert policy["script-src"] == ["'self'"]
    assert policy["object-src"] == ["'none'"]
    assert policy["base-uri"] == ["'self'"]
    assert policy["form-action"] == ["'self'"]
    assert policy["frame-ancestors"] == ["'none'"]
    assert policy["connect-src"] == ["'self'"]
    assert policy["font-src"] == ["'self'"]
    assert policy["img-src"] == ["'self'", "data:", "blob:"]
    assert "frame-src" not in policy


def test_scripts_never_get_inline_or_eval() -> None:
    for settings in (settings_for(), settings_for("firebase")):
        scripts = directives(content_security_policy(settings, ["'sha256-abc'"]))["script-src"]

        assert "'unsafe-inline'" not in scripts
        assert "'unsafe-eval'" not in scripts
        assert "'sha256-abc'" in scripts
        assert not any(source in ("*", "https:", "http:", "data:") for source in scripts)


def test_nothing_outside_this_origin_is_allowed_without_firebase() -> None:
    policy = content_security_policy(settings_for())

    assert "google" not in policy
    assert "http" not in policy


def test_firebase_sign_in_is_allowed_with_firebase_auth() -> None:
    policy = directives(content_security_policy(settings_for("firebase")))

    assert policy["script-src"] == ["'self'", "https://apis.google.com"]
    assert policy["connect-src"] == [
        "'self'",
        "https://identitytoolkit.googleapis.com",
        "https://securetoken.googleapis.com",
    ]
    assert policy["frame-src"] == ["https://cvitae-test.firebaseapp.com"]


def test_the_auth_iframe_is_the_configured_domain() -> None:
    settings = settings_for("firebase", firebase_auth_domain="cvitae.example.dev")

    policy = directives(content_security_policy(settings))

    assert policy["frame-src"] == ["https://cvitae.example.dev"]


async def test_the_served_policy_follows_the_settings(spa: Path) -> None:
    served = (await get(settings_for("firebase", static_dir=spa), "/")).headers[
        "content-security-policy"
    ]

    assert served == content_security_policy(settings_for("firebase"), inline_script_hashes(spa))


# The inline script that starts the SPA


def test_the_bootstrap_script_is_allowed_by_its_hash(spa: Path) -> None:
    assert inline_script_hashes(spa) == [sha256(BOOTSTRAP)]


async def test_the_hash_is_in_the_header_of_the_pages(spa: Path) -> None:
    for path in ("/", "/app/documents/123"):
        response = await get(settings_for(static_dir=spa), path)

        scripts = directives(response.headers["content-security-policy"])["script-src"]
        assert scripts == ["'self'", sha256(BOOTSTRAP)]


def test_only_scripts_that_run_inline_need_a_hash(tmp_path: Path) -> None:
    (tmp_path / "a.html").write_text(
        "<script>one()</script>"
        '<script src="/x.js"></script>'
        '<script type="module">two()</script>'
        '<script type="application/ld+json">{"a": 1}</script>'
        '<SCRIPT TYPE="text/javascript">three()</SCRIPT>'
        '<script type="text/template"><p>x</p></script>'
    )

    assert inline_script_hashes(tmp_path) == sorted(
        [sha256("one()"), sha256("two()"), sha256("three()")]
    )


def test_other_attributes_do_not_pass_for_the_type(tmp_path: Path) -> None:
    """`data-type` is not `type`: the script has no type, so it runs, and needs its hash."""
    (tmp_path / "a.html").write_text(
        '<script data-type="application/json">one()</script>'
        '<script data-type="x" type="module">two()</script>'
        '<script data-src="/x.js">three()</script>'
        '<script type="application/json" data-type="module">not_run()</script>'
    )

    assert inline_script_hashes(tmp_path) == sorted(
        [sha256("one()"), sha256("two()"), sha256("three()")]
    )


def test_the_type_is_read_as_the_browser_reads_it(tmp_path: Path) -> None:
    (tmp_path / "a.html").write_text(
        '<script type=" Module ">one()</script>'
        "<script type='text/javascript; charset=utf-8'>two()</script>"
        "<script type=>three()</script>"
        "<script type=importmap>{}</script>"
        '<script type="speculationrules">{}</script>'
        "<script type=text/x-template><b></b></script>"
    )

    assert inline_script_hashes(tmp_path) == sorted(
        [sha256("one()"), sha256("two()"), sha256("three()")]
    )


def test_a_script_is_hashed_whole(tmp_path: Path) -> None:
    body = 'if (a < b && "</p>" < "x") { fn("<div>", "&amp;") }\n\tlast()'
    (tmp_path / "a.html").write_text(f"<p>before</p><script>{body}</script><p>after</p>")

    assert inline_script_hashes(tmp_path) == [sha256(body)]


def test_line_breaks_are_hashed_as_the_browser_reads_them(tmp_path: Path) -> None:
    (tmp_path / "a.html").write_bytes(b"<script>a()\r\nb()\rc()</script>")

    assert inline_script_hashes(tmp_path) == [sha256("a()\nb()\nc()")]


def test_a_commented_out_script_is_not_hashed(tmp_path: Path) -> None:
    (tmp_path / "a.html").write_text("<!-- <script>old()</script> --><script>live()</script>")

    assert inline_script_hashes(tmp_path) == [sha256("live()")]


def test_pages_with_the_same_script_give_one_hash(tmp_path: Path) -> None:
    (tmp_path / "a.html").write_text("<script>same()</script>")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.html").write_text(
        "<p>x</p><script>same()</script><script>other()</script>"
    )

    assert inline_script_hashes(tmp_path) == sorted([sha256("same()"), sha256("other()")])


def test_no_pages_no_hashes(tmp_path: Path) -> None:
    assert inline_script_hashes(tmp_path) == []


def test_a_page_whose_script_changes_gets_the_new_hash(tmp_path: Path) -> None:
    page = tmp_path / "spa.html"
    page.write_text("<script>old()</script>")
    first = inline_script_hashes(tmp_path)
    page.write_text("<script>new()</script>")

    assert inline_script_hashes(tmp_path) != first == [sha256("old()")]


async def test_without_a_built_spa_scripts_are_this_origin_only() -> None:
    response = await get(settings_for(), "/api/v1/healthz")

    assert directives(response.headers["content-security-policy"])["script-src"] == ["'self'"]


# Swagger UI


async def test_the_api_docs_get_their_own_policy() -> None:
    response = await get(settings_for(), "/api/docs")

    assert response.status_code == 200
    assert response.headers["content-security-policy"] == DOCS_CSP
    assert "https://cdn.jsdelivr.net" in DOCS_CSP
    assert "frame-ancestors 'none'" in DOCS_CSP
    assert response.headers["x-content-type-options"] == "nosniff"


async def test_the_spa_policy_does_not_loosen_for_the_docs() -> None:
    response = await get(settings_for(), "/api/v1/healthz")

    policy = response.headers["content-security-policy"]
    assert "jsdelivr" not in policy
    assert "'unsafe-inline'" not in directives(policy)["script-src"]


# Errors nothing handled


async def test_an_unhandled_error_is_a_500_with_the_security_headers() -> None:
    """Starlette answers these from outside every middleware, so the handler adds the headers."""
    app = create_app(settings_for())

    @app.get("/api/v1/boom")
    async def boom() -> None:
        raise RuntimeError("secret detail for ada@example.com")

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        response = await c.get("/api/v1/boom")

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "internal_error",
            "message": "Something went wrong on the server. Try again.",
            "details": {},
        }
    }
    assert "secret" not in response.text
    headers = response.headers
    assert headers["content-security-policy"] == app.state.security.csp
    assert headers["strict-transport-security"] == "max-age=31536000; includeSubDomains"
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "permissions-policy" in headers
    assert len(headers.get_list("content-security-policy")) == 1


async def test_an_unhandled_error_still_reaches_the_server_to_be_logged() -> None:
    app = create_app(settings_for())

    @app.get("/api/v1/boom")
    async def boom() -> None:
        raise RuntimeError("logged by the server")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        with pytest.raises(RuntimeError, match="logged by the server"):
            await c.get("/api/v1/boom")


async def test_handled_errors_keep_their_own_answers() -> None:
    response = await get(settings_for(), "/api/v1/nothing-here")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
