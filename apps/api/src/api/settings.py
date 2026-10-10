"""Settings for the api, from environment variables (Secret Manager in GCP)."""

from pathlib import Path
from typing import Literal, Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """The part Alembic needs."""

    # Local development reads a git-ignored .env from the repository root, or from two levels up
    # when a command runs in apps/api (Alembic). Deployed environments set real variables.
    model_config = SettingsConfigDict(env_file=(".env", "../../.env"), extra="ignore")

    database_url: str
    """Pooled connection string used by the app (postgresql+psycopg://...)."""
    database_url_direct: str | None = None
    """Direct connection string for Alembic; falls back to database_url."""

    @property
    def migration_url(self) -> str:
        return self.database_url_direct or self.database_url


class Settings(DatabaseSettings):
    env: Literal["local", "test", "dev", "prod"]
    auth_mode: Literal["firebase", "dev"]
    renderer_url: str = "http://localhost:8001"
    static_dir: Path | None = None
    """Built SPA served at /. Unset in local development, where Vite serves the SPA."""

    @model_validator(mode="after")
    def _dev_auth_only_outside_cloud(self) -> Self:
        if self.auth_mode == "dev" and self.env in ("dev", "prod"):
            raise ValueError(f"AUTH_MODE=dev is not allowed when ENV={self.env}")
        return self
