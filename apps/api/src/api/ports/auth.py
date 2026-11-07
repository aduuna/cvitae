"""Who is calling: the AuthVerifier port, with FirebaseVerifier and DevVerifier (local only), and
ServiceAccountVerifier for the service that calls the `/internal` routes."""

import asyncio
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

import firebase_admin
from fastapi import Request
from firebase_admin import auth
from google.auth import exceptions as google_exceptions
from google.auth import transport as google_transport
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token

from api.errors import Forbidden, ServiceUnavailable, Unauthorized

DEV_USER_HEADER = "X-Dev-User"

type TokenVerifier = Callable[[str], Mapping[str, Any]]


@dataclass(frozen=True)
class Identity:
    uid: str
    email: str


class AuthVerifier(Protocol):
    async def verify(self, request: Request) -> Identity: ...


class ServiceCallerVerifier(Protocol):
    async def verify(self, request: Request) -> None:
        """Returns when the caller is the service allowed on `/internal` routes; raises
        `Unauthorized` or `Forbidden` otherwise."""
        ...


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


CLOCK_SKEW_SECONDS = 10
"""How far this instance's clock may differ from Google's. A token minted a moment ago is
otherwise refused as issued in the future when the clock is behind."""


class ServiceAccountVerifier:
    """Accepts a Google ID token minted for one audience by one service account, and nothing else:
    for the `/internal` routes, which Cloud Scheduler calls with an OIDC token from `scheduler-sa`.
    Firebase tokens, dev headers and tokens of any other account are refused."""

    def __init__(
        self,
        audience: str,
        service_account_email: str,
        transport: google_transport.Request | None = None,
    ) -> None:
        base = audience.strip().rstrip("/")
        if not base or not service_account_email:
            # Google's check skips the audience when it is empty.
            raise ValueError("an audience and a service account email are both needed")
        # The same URL with or without a trailing slash, whichever the scheduler job was given.
        self._audiences = [base, base + "/"]
        self._email = service_account_email.strip().lower()
        self._transport = transport or GoogleRequest()

    async def verify(self, request: Request) -> None:
        token = bearer_token(request)
        if token is None:
            raise Unauthorized("This route is for Google Cloud Scheduler.")
        try:
            # Checks the signature against Google's certificates, the expiry, the issuer and
            # that the token was minted for this audience.
            claims = await asyncio.to_thread(
                id_token.verify_oauth2_token,
                token,
                self._transport,
                self._audiences,
                CLOCK_SKEW_SECONDS,
            )
        except google_exceptions.TransportError as exc:
            raise ServiceUnavailable("The caller could not be checked. Try again.") from exc
        except (google_exceptions.GoogleAuthError, ValueError) as exc:
            raise Unauthorized("This route is for Google Cloud Scheduler.") from exc
        email = str(claims.get("email") or "").strip().lower()
        if claims.get("email_verified") is not True or email != self._email:
            raise Forbidden("This route is for Google Cloud Scheduler.")
