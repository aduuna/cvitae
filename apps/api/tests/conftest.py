import os

# api.main builds an app from the environment on import, so configure it first.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://vitae:vitae@localhost:5432/vitae_test"
)
os.environ.update(
    ENV="test",
    AUTH_MODE="dev",
    DATABASE_URL=TEST_DATABASE_URL,
    RENDERER_URL="http://renderer.test",
)

import json
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from psycopg import sql
from sqlalchemy import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from api.deps import get_renderer, get_session
from api.main import create_app
from api.ports.renderer import FakeRendererClient

REPO = Path(__file__).resolve().parents[3]
FIXTURES = REPO / "templates" / "fixtures"


def _create_database(url: str) -> None:
    target = make_url(url)
    name = target.database or "vitae_test"
    admin = target.set(drivername="postgresql", database="postgres")
    with psycopg.connect(admin.render_as_string(hide_password=False), autocommit=True) as conn:
        found = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,)).fetchone()
        if not found:
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))


@pytest.fixture(scope="session")
def alembic_config() -> Config:
    config = Config(str(REPO / "apps" / "api" / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    config.attributes["configure_logging"] = False
    return config


@pytest.fixture(scope="session")
def database(alembic_config: Config) -> str:
    """A test database migrated from scratch, which also exercises downgrade and upgrade."""
    _create_database(TEST_DATABASE_URL)
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")
    return TEST_DATABASE_URL


@pytest.fixture
async def db_session(database: str) -> AsyncIterator[AsyncSession]:
    """A session inside a transaction that is rolled back after the test. Commits in the code
    under test only release savepoints."""
    engine = create_async_engine(database, poolclass=NullPool)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()
    await engine.dispose()


@pytest.fixture
def renderer() -> FakeRendererClient:
    return FakeRendererClient()


@pytest.fixture
def app(db_session: AsyncSession, renderer: FakeRendererClient) -> FastAPI:
    app = create_app()

    async def session_override() -> AsyncIterator[AsyncSession]:
        try:
            yield db_session
            await db_session.commit()
        except BaseException:
            await db_session.rollback()
            raise

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[get_renderer] = lambda: renderer
    return app


@pytest.fixture
def make_client(app: FastAPI) -> Callable[..., AsyncClient]:
    def make(user: str | None = "ada@example.com") -> AsyncClient:
        headers = {"X-Dev-User": user} if user else {}
        return AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test", headers=headers
        )

    return make


@pytest.fixture
async def client(make_client: Callable[..., AsyncClient]) -> AsyncIterator[AsyncClient]:
    async with make_client() as c:
        yield c


@pytest.fixture
async def other_client(make_client: Callable[..., AsyncClient]) -> AsyncIterator[AsyncClient]:
    async with make_client("bob@example.com") as c:
        yield c


@pytest.fixture
def sample_content() -> dict[str, Any]:
    """The sample profile fixture: one page, one placeholder."""
    return json.loads((FIXTURES / "profile-sample.json").read_text())
