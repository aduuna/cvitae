from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from api.main import create_app


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
