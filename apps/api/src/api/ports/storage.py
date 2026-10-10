"""The storage port: uploaded files by key. GCS in the cloud, a local directory otherwise."""

import asyncio
import contextlib
from pathlib import Path, PurePosixPath
from typing import Protocol

from google.api_core.exceptions import NotFound as GcsNotFound
from google.cloud import storage

from api.errors import NotFound


def check_key(key: str) -> str:
    """Keys are relative POSIX paths without `.` or `..` parts."""
    path = PurePosixPath(key)
    if not key or path.is_absolute() or any(part in ("", ".", "..") for part in key.split("/")):
        raise ValueError(f"invalid storage key: {key!r}")
    return key


class Storage(Protocol):
    async def put(self, key: str, data: bytes, content_type: str) -> None: ...

    async def get(self, key: str) -> bytes:
        """The object's bytes; NotFound when there is none."""
        ...

    async def delete(self, key: str) -> None:
        """Remove the object; no error when it is already gone."""
        ...

    async def delete_prefix(self, prefix: str) -> int:
        """Remove every object under `prefix`; the number removed."""
        ...


class GcsStorage:
    """A bucket via the google-cloud-storage client, whose blocking calls run in threads."""

    def __init__(self, bucket: str, client: storage.Client | None = None) -> None:
        self._bucket = (client or storage.Client()).bucket(bucket)

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        blob = self._bucket.blob(check_key(key))
        await asyncio.to_thread(blob.upload_from_string, data, content_type=content_type)

    async def get(self, key: str) -> bytes:
        blob = self._bucket.blob(check_key(key))
        try:
            return await asyncio.to_thread(blob.download_as_bytes)
        except GcsNotFound as exc:
            raise NotFound("This file does not exist or was deleted.") from exc

    async def delete(self, key: str) -> None:
        blob = self._bucket.blob(check_key(key))
        with contextlib.suppress(GcsNotFound):
            await asyncio.to_thread(blob.delete)

    async def delete_prefix(self, prefix: str) -> int:
        check_key(prefix.rstrip("/"))

        def remove_all() -> int:
            blobs = list(self._bucket.list_blobs(prefix=prefix.rstrip("/") + "/"))
            for blob in blobs:
                blob.delete()
            return len(blobs)

        return await asyncio.to_thread(remove_all)


class LocalStorage:
    """Files under a directory, for local development and tests."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def _path(self, key: str) -> Path:
        return self._root / check_key(key)

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    async def get(self, key: str) -> bytes:
        path = self._path(key)
        if not path.is_file():
            raise NotFound("This file does not exist or was deleted.")
        return path.read_bytes()

    async def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    async def delete_prefix(self, prefix: str) -> int:
        folder = self._path(prefix.rstrip("/"))
        files = [path for path in folder.rglob("*") if path.is_file()] if folder.is_dir() else []
        for path in files:
            path.unlink()
        return len(files)
