"""POST /internal/prune-versions: only Cloud Scheduler's service account gets in, and only
autosave versions older than a week go.

Tokens are signed with a throwaway key and checked by Google's own verification code against a
certificate served by a stub transport, so the audience, issuer, expiry and signature checks are
the real ones. Nothing calls Google."""

import json
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from fastapi import FastAPI
from google.auth import crypt, jwt
from google.auth import transport as google_transport
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import DocumentVersion
from api.main import build_scheduler_verifier
from api.ports.auth import ServiceAccountVerifier
from api.repositories.documents import (
    DocumentRepository,
    DocumentVersionRepository,
    VersionPruner,
)
from api.repositories.users import UserRepository
from api.services import versions as service
from api.settings import Settings

URL = "/api/v1/internal/prune-versions"
AUDIENCE = "https://cvitae.example.dev"
SCHEDULER = "scheduler-sa@cvitae-test.iam.gserviceaccount.com"
KEY_ID = "test-key"
CONTENT: dict[str, Any] = {
    "schema_version": 1,
    "basics": {"name": "A"},
    "summary": "",
    "sections": [],
}


def _make_key() -> tuple[rsa.RSAPrivateKey, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test")])
    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    return key, cert.public_bytes(serialization.Encoding.PEM).decode()


KEY, CERT = _make_key()
SIGNER = crypt.RSASigner.from_string(
    KEY.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ),
    KEY_ID,
)
OTHER_KEY, _ = _make_key()
OTHER_SIGNER = crypt.RSASigner.from_string(
    OTHER_KEY.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ),
    KEY_ID,
)


class GoogleCerts(google_transport.Request):
    """Serves the test certificate where Google's would be; fails like an outage on request."""

    def __init__(self, *, down: bool = False) -> None:
        self.down = down
        self.calls = 0

    def __call__(self, url: str, method: str = "GET", *args: Any, **kwargs: Any) -> Any:
        self.calls += 1
        assert url.startswith("https://www.googleapis.com/")
        status = 503 if self.down else 200
        data = json.dumps({KEY_ID: CERT}).encode()
        return type("Response", (), {"status": status, "data": data, "headers": {}})()


def token(
    *,
    email: str = SCHEDULER,
    audience: str = AUDIENCE,
    issuer: str = "https://accounts.google.com",
    email_verified: bool = True,
    expires_in: int = 3600,
    signer: crypt.Signer = SIGNER,
    **extra: Any,
) -> str:
    now = int(time.time())
    claims = {
        "iss": issuer,
        "aud": audience,
        "sub": "1234567890",
        "email": email,
        "email_verified": email_verified,
        "iat": now - 10,
        "exp": now + expires_in,
        **extra,
    }
    return jwt.encode(signer, claims, key_id=KEY_ID).decode()


def bearer(value: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {value}"}


@pytest.fixture
def settings(settings: Settings) -> Settings:
    settings.public_base_url = AUDIENCE
    settings.scheduler_sa_email = SCHEDULER
    return settings


@pytest.fixture
def certs() -> GoogleCerts:
    return GoogleCerts()


@pytest.fixture(autouse=True)
def google_certs(app: FastAPI, certs: GoogleCerts) -> None:
    """The app checks tokens against the test certificate, not Google's."""
    app.state.scheduler_verifier = ServiceAccountVerifier(AUDIENCE, SCHEDULER, transport=certs)


@dataclass(frozen=True)
class Made:
    id: uuid.UUID
    reason: str
    age: timedelta


WEEK = timedelta(days=7)


async def make_versions(session: AsyncSession, now: datetime) -> list[Made]:
    """Versions of two users' CVs: every reason, young and old, either side of a week."""
    made: list[Made] = []
    for email in ("ada@example.com", "bob@example.com"):
        owner = await UserRepository(session).get_or_create(f"dev:{email}", email)
        document = await DocumentRepository(session, owner.id).create(
            name="CV", template_id="classic", content=CONTENT
        )
        versions = DocumentVersionRepository(session, owner.id)
        for reason, age in (
            ("autosave", timedelta(days=30)),
            ("autosave", WEEK + timedelta(seconds=1)),
            ("autosave", WEEK - timedelta(seconds=1)),
            ("autosave", timedelta(hours=1)),
            ("manual", timedelta(days=90)),
            ("tailor", timedelta(days=90)),
            ("restore", timedelta(days=90)),
        ):
            row = await versions.create(
                document_id=document.id, reason=reason, content=CONTENT, created_at=now - age
            )
            made.append(Made(row.id, reason, age))
    await session.commit()
    return made


def survivors(made: list[Made], extra_age: timedelta = timedelta(0)) -> set[uuid.UUID]:
    """What pruning leaves, by the rule: every version but an autosave older than a week."""
    return {v.id for v in made if not (v.reason == "autosave" and v.age + extra_age > WEEK)}


async def remaining(session: AsyncSession) -> set[uuid.UUID]:
    return set(await session.scalars(select(DocumentVersion.id)))


# The caller


async def test_scheduler_prunes_old_autosaves_and_nothing_else(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    made = await make_versions(db_session, datetime.now(UTC))

    response = await client.post(URL, headers=bearer(token()))

    assert response.status_code == 200
    # Two old autosaves of each user's CV; the autosaves just inside the week stay.
    assert response.json() == {"deleted": 4}
    assert await remaining(db_session) == survivors(made)
    assert len(await remaining(db_session)) == len(made) - 4


async def test_a_second_run_finds_nothing_to_prune(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await make_versions(db_session, datetime.now(UTC))
    await client.post(URL, headers=bearer(token()))

    response = await client.post(URL, headers=bearer(token()))

    assert response.json() == {"deleted": 0}


async def refused(
    client: AsyncClient, db_session: AsyncSession, status: int, **request: Any
) -> dict[str, Any]:
    made = await make_versions(db_session, datetime.now(UTC))

    response = await client.post(URL, **request)

    assert response.status_code == status
    assert await remaining(db_session) == {v.id for v in made}
    return response.json()["error"]


async def test_a_call_without_a_token_is_refused(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    error = await refused(client, db_session, 401)

    assert error["code"] == "unauthorized"


async def test_a_signed_in_user_is_refused(client: AsyncClient, db_session: AsyncSession) -> None:
    """`client` sends X-Dev-User, which signs a user in on every other route."""
    await refused(client, db_session, 401, headers={"X-Dev-User": "ada@example.com"})


async def test_a_firebase_token_is_refused(client: AsyncClient, db_session: AsyncSession) -> None:
    """A Firebase ID token is a Google-signed JWT too, but for the Firebase project and from
    its own issuer. Signed here with the key the verifier trusts, so only its claims set it
    apart."""
    firebase = token(
        issuer="https://securetoken.google.com/cvitae-test",
        audience="cvitae-test",
        user_id="uid-1",
        firebase={"sign_in_provider": "google.com"},
    )

    await refused(client, db_session, 401, headers=bearer(firebase))


async def test_a_firebase_token_for_the_apis_audience_is_still_refused(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Even with the audience right, Firebase's issuer is not Google's accounts issuer."""
    firebase = token(issuer="https://securetoken.google.com/cvitae-test")

    await refused(client, db_session, 401, headers=bearer(firebase))


async def test_another_service_account_is_refused(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    other = token(email="someone-else@cvitae-test.iam.gserviceaccount.com")

    error = await refused(client, db_session, 403, headers=bearer(other))

    assert error["code"] == "forbidden"


async def test_the_account_is_compared_without_regard_to_case(client: AsyncClient) -> None:
    response = await client.post(URL, headers=bearer(token(email=SCHEDULER.upper())))

    assert response.status_code == 200


async def test_an_unverified_email_is_refused(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await refused(client, db_session, 403, headers=bearer(token(email_verified=False)))


async def test_a_token_without_an_email_is_refused(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await refused(client, db_session, 403, headers=bearer(token(email="")))


async def test_a_token_for_another_audience_is_refused(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await refused(
        client, db_session, 401, headers=bearer(token(audience="https://elsewhere.example.dev"))
    )


async def test_the_audience_is_the_apis_url_not_the_route(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    other = token(audience=AUDIENCE + "/api/v1/internal/prune-versions")

    await refused(client, db_session, 401, headers=bearer(other))


async def test_an_expired_token_is_refused(client: AsyncClient, db_session: AsyncSession) -> None:
    await refused(client, db_session, 401, headers=bearer(token(expires_in=-120)))


async def test_a_token_signed_with_another_key_is_refused(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await refused(client, db_session, 401, headers=bearer(token(signer=OTHER_SIGNER)))


@pytest.mark.parametrize("value", ["garbage", "a.b.c", "Bearer"])
async def test_a_malformed_token_is_refused(
    client: AsyncClient, db_session: AsyncSession, value: str
) -> None:
    await refused(client, db_session, 401, headers=bearer(value))


async def test_other_schemes_are_refused(client: AsyncClient, db_session: AsyncSession) -> None:
    await refused(client, db_session, 401, headers={"Authorization": f"Basic {token()}"})


async def test_googles_certificates_being_out_of_reach_is_not_a_pass(
    app: FastAPI, client: AsyncClient, db_session: AsyncSession
) -> None:
    app.state.scheduler_verifier = ServiceAccountVerifier(
        AUDIENCE, SCHEDULER, transport=GoogleCerts(down=True)
    )

    error = await refused(client, db_session, 503, headers=bearer(token()))

    assert error["code"] == "service_unavailable"


async def test_without_the_settings_every_call_is_refused(
    app: FastAPI, client: AsyncClient, db_session: AsyncSession
) -> None:
    app.state.scheduler_verifier = None

    error = await refused(client, db_session, 503, headers=bearer(token()))

    assert error["code"] == "service_unavailable"


def test_the_verifier_needs_an_audience_and_an_account() -> None:
    """Google's check skips the audience when it is empty, so an empty one is not allowed."""
    with pytest.raises(ValueError, match="both needed"):
        ServiceAccountVerifier("", SCHEDULER)
    with pytest.raises(ValueError, match="both needed"):
        ServiceAccountVerifier(AUDIENCE, "")


def test_the_verifier_is_built_from_the_settings(settings: Settings) -> None:
    settings.public_base_url = AUDIENCE + "/"

    verifier = build_scheduler_verifier(settings)

    assert isinstance(verifier, ServiceAccountVerifier)
    assert verifier._audience == AUDIENCE


@pytest.mark.parametrize(
    ("url", "email"), [(None, None), (AUDIENCE, None), (None, SCHEDULER), ("", SCHEDULER)]
)
def test_no_verifier_without_both_settings(
    settings: Settings, url: str | None, email: str | None
) -> None:
    settings.public_base_url = url
    settings.scheduler_sa_email = email

    assert build_scheduler_verifier(settings) is None


# What is pruned


async def test_pruning_keeps_what_the_rule_keeps(db_session: AsyncSession) -> None:
    now = datetime.now(UTC)
    made = await make_versions(db_session, now)

    deleted = await service.prune_autosaves(VersionPruner(db_session), now)

    assert deleted == 4
    assert await remaining(db_session) == survivors(made)
    left = await db_session.scalars(select(DocumentVersion.reason))
    assert set(left) == {"autosave", "manual", "tailor", "restore"}


async def test_a_week_is_counted_from_the_time_given(db_session: AsyncSession) -> None:
    now = datetime(2026, 11, 7, 3, 0, tzinfo=UTC)
    made = await make_versions(db_session, now)
    later = timedelta(days=8)

    # Eight days on, every autosave is older than a week, the one of an hour ago too.
    deleted = await service.prune_autosaves(VersionPruner(db_session), now + later)

    assert deleted == 8
    assert await remaining(db_session) == survivors(made, later)
    assert len(await remaining(db_session)) == len(made) - 8
