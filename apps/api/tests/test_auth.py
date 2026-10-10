"""FirebaseVerifier: bearer tokens, claims and error mapping. Token checks are faked except for
malformed tokens, which firebase-admin rejects without a network call."""

from collections.abc import Mapping
from typing import Any

import pytest
from firebase_admin import auth
from starlette.requests import Request

from api.errors import ServiceUnavailable, Unauthorized
from api.ports.auth import FirebaseVerifier, bearer_token

CLAIMS = {"uid": "firebase-uid-1", "email": "Ada@Example.com", "email_verified": True}


def request_with(headers: dict[str, str]) -> Request:
    raw = [(name.lower().encode(), value.encode()) for name, value in headers.items()]
    return Request({"type": "http", "headers": raw})


def verifier_returning(claims: Mapping[str, Any]) -> FirebaseVerifier:
    return FirebaseVerifier("cvitae-test", verify_token=lambda _: claims)


def verifier_raising(error: Exception) -> FirebaseVerifier:
    def verify(_: str) -> Mapping[str, Any]:
        raise error

    return FirebaseVerifier("cvitae-test", verify_token=verify)


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("Bearer abc", "abc"),
        ("bearer  abc ", "abc"),
        ("Basic abc", None),
        ("Bearer ", None),
        ("", None),
    ],
)
def test_bearer_token(header: str, expected: str | None) -> None:
    assert bearer_token(request_with({"Authorization": header})) == expected


async def test_a_valid_token_identifies_the_user() -> None:
    seen: list[str] = []

    def verify(token: str) -> Mapping[str, Any]:
        seen.append(token)
        return CLAIMS

    identity = await FirebaseVerifier("p", verify_token=verify).verify(
        request_with({"Authorization": "Bearer token-1"})
    )

    assert seen == ["token-1"]
    assert (identity.uid, identity.email) == ("firebase-uid-1", "ada@example.com")


async def test_no_token_is_unauthorized() -> None:
    with pytest.raises(Unauthorized, match="Sign in to continue"):
        await verifier_returning(CLAIMS).verify(request_with({}))


@pytest.mark.parametrize(
    "claims",
    [
        {"uid": "u", "email": "a@example.com", "email_verified": False},
        {"uid": "u", "email_verified": True},
        {"uid": "u", "email": " ", "email_verified": True},
    ],
)
async def test_tokens_without_a_verified_email_are_refused(claims: dict[str, Any]) -> None:
    with pytest.raises(Unauthorized, match="verified email"):
        await verifier_returning(claims).verify(request_with({"Authorization": "Bearer t"}))


@pytest.mark.parametrize(
    "error",
    [
        auth.InvalidIdTokenError("bad"),
        auth.ExpiredIdTokenError("expired", cause=None),
        ValueError("malformed"),
    ],
)
async def test_invalid_tokens_are_unauthorized(error: Exception) -> None:
    with pytest.raises(Unauthorized, match="session has expired"):
        await verifier_raising(error).verify(request_with({"Authorization": "Bearer t"}))


async def test_unreachable_google_keys_are_a_service_error() -> None:
    error = auth.CertificateFetchError("no keys", cause=None)

    with pytest.raises(ServiceUnavailable):
        await verifier_raising(error).verify(request_with({"Authorization": "Bearer t"}))


@pytest.mark.parametrize("token", ["garbage", "a.b.c"])
async def test_the_real_verifier_rejects_malformed_tokens(token: str) -> None:
    verifier = FirebaseVerifier("cvitae-test")

    with pytest.raises(Unauthorized):
        await verifier.verify(request_with({"Authorization": f"Bearer {token}"}))


def test_the_real_verifier_reuses_its_firebase_app() -> None:
    FirebaseVerifier("cvitae-reuse")
    FirebaseVerifier("cvitae-reuse")
