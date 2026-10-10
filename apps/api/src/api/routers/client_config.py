"""What the SPA needs before anyone signs in: how to sign in. Public; nothing here is secret."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from api.deps import AppSettings

router = APIRouter(prefix="/client-config", tags=["client-config"])


class FirebaseConfig(BaseModel):
    api_key: str
    auth_domain: str
    project_id: str
    app_id: str


class ClientConfig(BaseModel):
    auth_mode: Literal["firebase", "dev"]
    firebase: FirebaseConfig | None
    """Set when auth_mode is firebase."""


@router.get("")
async def get_client_config(settings: AppSettings) -> ClientConfig:
    firebase = None
    if settings.auth_mode == "firebase":
        firebase = FirebaseConfig(
            api_key=settings.firebase_api_key or "",
            auth_domain=settings.firebase_auth_domain or "",
            project_id=settings.firebase_project_id or "",
            app_id=settings.firebase_app_id or "",
        )
    return ClientConfig(auth_mode=settings.auth_mode, firebase=firebase)
