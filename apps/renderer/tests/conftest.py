import json
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from cvcore.models import CvContent
from cvcore.render import to_render_json
from renderer.main import app, get_settings
from renderer.settings import Settings

FIXTURES = Path(__file__).resolve().parents[3] / "templates" / "fixtures"


def load_fixture(name: str) -> dict[str, Any]:
    """A profile fixture as the renderer's data.json."""
    content = CvContent.model_validate_json((FIXTURES / f"{name}.json").read_text())
    return to_render_json(content)


@pytest.fixture
def data_json() -> Callable[..., str]:
    """data.json text for a fixture (default: the sample profile)."""
    return lambda name="profile-sample": json.dumps(load_fixture(name))


@pytest.fixture
def make_client() -> Callable[..., AsyncClient]:
    """An ASGI client whose renderer uses the given settings overrides."""

    def make(**overrides: Any) -> AsyncClient:
        settings = Settings(**overrides)
        app.dependency_overrides[get_settings] = lambda: settings
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://renderer.test")

    return make


@pytest.fixture
async def client(make_client: Callable[..., AsyncClient]) -> AsyncIterator[AsyncClient]:
    async with make_client() as c:
        yield c
    app.dependency_overrides.clear()
