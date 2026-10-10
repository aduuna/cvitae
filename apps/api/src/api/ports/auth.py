"""Who is calling: the AuthVerifier port, with FirebaseVerifier and DevVerifier (local only)."""

import asyncio
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

import firebase_admin
from fastapi import Request
from firebase_admin import auth

from api.errors import ServiceUnavailable, Unauthorized

DEV_USER_HEADER = "X-Dev-User"

type TokenVerifier = Callable[[str], Mapping[str, Any]]


@dataclass(frozen=True)
class Identity:
    uid: str
    email: str


class AuthVerifier(Protocol):
    async def verify(self, request: Request) -> Identity: ...


def bearer_token(request: Request) -> str | None:
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    token = token.strip()
    return token if scheme.lower() == "bearer" and token else None


class FirebaseVerifier:
    """Checks `Authorization: Bearer <Firebase ID token>`: signature, expiry and that the token
    was issued for this project. The users of this app always have a verified email."""

    def __init__(self, project_id: str, verify_token: TokenVerifier | None = None) -> None:
        self._verify_token = verify_token or self._firebase_verifier(project_id)

    @staticmethod
    def _firebase_verifier(project_id: str) -> TokenVerifier:
        name = f"verifier-{project_id}"
        try:
            app = firebase_admin.get_app(name)
        except ValueError:
            # Verifying ID tokens needs only the project id and Google's public keys.
            app = firebase_admin.initialize_app(options={"projectId": project_id}, name=name)
        return lambda token: auth.verify_id_token(token, app=app)

    async def verify(self, request: Request) -> Identity:
        token = bearer_token(request)
        if token is None:
            raise Unauthorized("Sign in to continue.")
        try:
            claims = await asyncio.to_thread(self._verify_token, token)
        except auth.CertificateFetchError as exc:
            raise ServiceUnavailable("Sign-in could not be checked. Try again.") from exc
        except (auth.InvalidIdTokenError, ValueError) as exc:
            raise Unauthorized("Your session has expired. Sign in again.") from exc
        email = str(claims.get("email") or "").strip().lower()
        if not email or not claims.get("email_verified"):
            raise Unauthorized("Sign in with a verified email address.")
        return Identity(uid=str(claims["uid"]), email=email)


class DevVerifier:
    """Trusts an `X-Dev-User: <email>` header. Settings refuse this mode in deployed envs."""

    async def verify(self, request: Request) -> Identity:
        email = request.headers.get(DEV_USER_HEADER, "").strip().lower()
        if "@" not in email:
            raise Unauthorized(
                f"Sign in to continue. In dev mode, send an {DEV_USER_HEADER} header."
            )
        return Identity(uid=f"dev:{email}", email=email)
