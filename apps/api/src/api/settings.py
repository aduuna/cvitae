"""Settings for the api, from environment variables (Secret Manager in GCP)."""

from pathlib import Path
from typing import Literal, Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO = Path(__file__).resolve().parents[4]


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

    firebase_project_id: str | None = None
    """Audience of Firebase ID tokens; required with AUTH_MODE=firebase."""
    # The SPA's Firebase web config, served by GET /api/v1/client-config. Not secret.
    firebase_api_key: str | None = None
    firebase_auth_domain: str | None = None
    firebase_app_id: str | None = None

    storage_mode: Literal["gcs", "local"] = "local"
    gcs_bucket: str | None = None
    local_storage_dir: Path = _REPO / ".data" / "uploads"

    renderer_url: str = "http://localhost:8001"
    renderer_auth: Literal["oidc", "none"] = "none"
    """`oidc`: call the renderer with a Google ID token for its URL (Cloud Run IAM)."""

    sample_profile_path: Path = _REPO / "templates" / "fixtures" / "profile-sample.json"
    """Shown in template previews when the user has no profile yet."""

    static_dir: Path | None = None
    """Built SPA served at /. Unset in local development, where Vite serves the SPA."""

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.auth_mode == "dev" and self.env in ("dev", "prod"):
            raise ValueError(f"AUTH_MODE=dev is not allowed when ENV={self.env}")
        if self.auth_mode == "firebase":
            firebase = {
                "FIREBASE_PROJECT_ID": self.firebase_project_id,
                "FIREBASE_API_KEY": self.firebase_api_key,
                "FIREBASE_AUTH_DOMAIN": self.firebase_auth_domain,
                "FIREBASE_APP_ID": self.firebase_app_id,
            }
            if missing := [name for name, value in firebase.items() if not value]:
                raise ValueError(f"AUTH_MODE=firebase needs {', '.join(missing)}")
        if self.storage_mode == "gcs" and not self.gcs_bucket:
            raise ValueError("STORAGE_MODE=gcs needs GCS_BUCKET")
        return self
