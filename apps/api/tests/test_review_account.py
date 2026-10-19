"""scripts/review_account.py, against a stand-in for the Firebase Admin SDK."""

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from firebase_admin import auth

SCRIPT = Path(__file__).parents[1] / "scripts" / "review_account.py"


@pytest.fixture
def script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("review_account", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeUsers:
    def __init__(self, *, exists: bool) -> None:
        self.exists = exists
        self.created: dict[str, Any] | None = None
        self.updated: dict[str, Any] | None = None

    def update_user(self, uid: str, **fields: Any) -> None:
        if not self.exists:
            raise auth.UserNotFoundError("no user")
        self.updated = {"uid": uid, **fields}

    def create_user(self, **fields: Any) -> None:
        self.created = fields


def install(monkeypatch: pytest.MonkeyPatch, script: ModuleType, users: FakeUsers) -> None:
    monkeypatch.setattr(script.auth, "update_user", users.update_user)
    monkeypatch.setattr(script.auth, "create_user", users.create_user)


def test_creates_a_verified_user_with_the_password(
    monkeypatch: pytest.MonkeyPatch, script: ModuleType
) -> None:
    users = FakeUsers(exists=False)
    install(monkeypatch, script, users)
    password = script.new_password()

    assert script.set_up(None, "cvitae-review@aduuna.dev", password) is True

    assert users.created == {
        "uid": "cvitae-review",
        "email": "cvitae-review@aduuna.dev",
        "password": password,
        "email_verified": True,
        "app": None,
    }


def test_resets_the_password_of_the_existing_user(
    monkeypatch: pytest.MonkeyPatch, script: ModuleType
) -> None:
    users = FakeUsers(exists=True)
    install(monkeypatch, script, users)
    password = script.new_password()

    assert script.set_up(None, "cvitae-review@aduuna.dev", password) is False

    assert users.created is None
    assert users.updated == {
        "uid": "cvitae-review",
        "email": "cvitae-review@aduuna.dev",
        "password": password,
        "email_verified": True,
        "disabled": False,
        "app": None,
    }


def test_passwords_are_long_and_new_each_time(script: ModuleType) -> None:
    passwords = {script.new_password() for _ in range(5)}

    assert len(passwords) == 5
    assert all(len(password) >= 20 for password in passwords)
