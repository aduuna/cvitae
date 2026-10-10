"""Storage port: LocalStorage on disk, GcsStorage against an in-memory stand-in for the client."""

from pathlib import Path
from typing import Any

import pytest
from google.api_core.exceptions import NotFound as GcsNotFound

from api.errors import NotFound
from api.ports.storage import GcsStorage, LocalStorage, Storage, check_key


class FakeBlob:
    def __init__(self, objects: dict[str, tuple[bytes, str]], name: str) -> None:
        self.objects = objects
        self.name = name

    def upload_from_string(self, data: bytes, content_type: str) -> None:
        self.objects[self.name] = (data, content_type)

    def download_as_bytes(self) -> bytes:
        if self.name not in self.objects:
            raise GcsNotFound("missing")
        return self.objects[self.name][0]

    def delete(self) -> None:
        if self.objects.pop(self.name, None) is None:
            raise GcsNotFound("missing")


class FakeBucket:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}

    def blob(self, name: str) -> FakeBlob:
        return FakeBlob(self.objects, name)

    def list_blobs(self, prefix: str) -> list[FakeBlob]:
        return [self.blob(name) for name in list(self.objects) if name.startswith(prefix)]


class FakeClient:
    def __init__(self) -> None:
        self.buckets: dict[str, FakeBucket] = {}

    def bucket(self, name: str) -> FakeBucket:
        return self.buckets.setdefault(name, FakeBucket())


@pytest.fixture(params=["local", "gcs"])
def storage(request: pytest.FixtureRequest, tmp_path: Path) -> Storage:
    if request.param == "local":
        return LocalStorage(tmp_path)
    client: Any = FakeClient()
    return GcsStorage("uploads", client=client)


async def test_put_then_get(storage: Storage) -> None:
    await storage.put("uploads/u1/a", b"%PDF-1.7", "application/pdf")

    assert await storage.get("uploads/u1/a") == b"%PDF-1.7"


async def test_get_missing_is_not_found(storage: Storage) -> None:
    with pytest.raises(NotFound):
        await storage.get("uploads/u1/missing")


async def test_delete_is_idempotent(storage: Storage) -> None:
    await storage.put("uploads/u1/a", b"x", "application/pdf")

    await storage.delete("uploads/u1/a")
    await storage.delete("uploads/u1/a")

    with pytest.raises(NotFound):
        await storage.get("uploads/u1/a")


async def test_delete_prefix_removes_only_that_prefix(storage: Storage) -> None:
    for key in ["uploads/u1/a", "uploads/u1/b", "uploads/u10/c", "uploads/u2/d"]:
        await storage.put(key, b"x", "application/pdf")

    assert await storage.delete_prefix("uploads/u1") == 2
    assert await storage.delete_prefix("uploads/u1/") == 0
    assert await storage.get("uploads/u10/c") == b"x"
    assert await storage.get("uploads/u2/d") == b"x"


async def test_gcs_records_the_content_type() -> None:
    client = FakeClient()
    fake: Any = client
    storage = GcsStorage("uploads", client=fake)

    await storage.put("uploads/u1/a", b"x", "application/pdf")

    assert client.buckets["uploads"].objects["uploads/u1/a"] == (b"x", "application/pdf")


@pytest.mark.parametrize("key", ["", "/abs", "a/../b", "a//b", "./a", "a/"])
def test_keys_cannot_escape(key: str) -> None:
    with pytest.raises(ValueError, match="invalid storage key"):
        check_key(key)


async def test_local_storage_rejects_escaping_keys(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="invalid storage key"):
        await LocalStorage(tmp_path / "root").put("../outside", b"x", "text/plain")
