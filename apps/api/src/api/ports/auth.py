"""Who is calling: the AuthVerifier port. Firebase arrives in M2; DevVerifier is for local use."""

from dataclasses import dataclass
from typing import Protocol

from fastapi import Request

from api.errors import Unauthorized

DEV_USER_HEADER = "X-Dev-User"


@dataclass(frozen=True)
class Identity:
    uid: str
    email: str


class AuthVerifier(Protocol):
    async def verify(self, request: Request) -> Identity: ...


class DevVerifier:
    """Trusts an `X-Dev-User: <email>` header. Settings refuse this mode in deployed envs."""

    async def verify(self, request: Request) -> Identity:
        email = request.headers.get(DEV_USER_HEADER, "").strip().lower()
        if "@" not in email:
            raise Unauthorized(
                f"Sign in to continue. In dev mode, send an {DEV_USER_HEADER} header."
            )
        return Identity(uid=f"dev:{email}", email=email)
