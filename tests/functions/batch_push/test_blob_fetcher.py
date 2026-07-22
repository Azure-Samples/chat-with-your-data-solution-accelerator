"""Tests for src/functions/batch_push/blob_fetcher.py."""

import logging
from typing import cast

import pytest
from azure.core.exceptions import AzureError, ResourceNotFoundError
from azure.storage.blob.aio import ContainerClient

from functions.batch_push.blob_fetcher import download_blob


class _FakeDownloader:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    async def readall(self) -> bytes:
        return self._payload


class _FakeContainerClient:
    """Minimal async stand-in for ``ContainerClient``.

    Only ``container_name`` (used in the error log) and
    ``download_blob`` (the SDK call) are modeled.
    """

    def __init__(
        self,
        *,
        container_name: str = "documents",
        payload: bytes = b"",
        raises: AzureError | None = None,
    ) -> None:
        self.container_name = container_name
        self._payload = payload
        self._raises = raises
        self.calls: list[str] = []

    async def download_blob(self, blob: str) -> _FakeDownloader:
        self.calls.append(blob)
        if self._raises is not None:
            raise self._raises
        return _FakeDownloader(self._payload)


def _as_container(fake: _FakeContainerClient) -> ContainerClient:
    return cast(ContainerClient, fake)


@pytest.mark.asyncio
async def test_returns_blob_bytes() -> None:
    fake = _FakeContainerClient(payload=b"hello world")
    result = await download_blob(_as_container(fake), "doc.pdf")
    assert result == b"hello world"
    assert fake.calls == ["doc.pdf"]


@pytest.mark.asyncio
async def test_empty_blob_returns_empty_bytes() -> None:
    fake = _FakeContainerClient(payload=b"")
    result = await download_blob(_as_container(fake), "empty.txt")
    assert result == b""


@pytest.mark.asyncio
async def test_passes_filename_through_unchanged() -> None:
    fake = _FakeContainerClient(payload=b"x")
    await download_blob(_as_container(fake), "2026/contracts/q1.pdf")
    assert fake.calls == ["2026/contracts/q1.pdf"]


@pytest.mark.asyncio
async def test_azure_error_is_logged_and_reraised(
    caplog: pytest.LogCaptureFixture,
) -> None:
    fake = _FakeContainerClient(
        container_name="docs",
        raises=ResourceNotFoundError("not found"),
    )
    caplog.set_level(logging.ERROR, logger="functions.batch_push.blob_fetcher")
    with pytest.raises(ResourceNotFoundError):
        await download_blob(_as_container(fake), "missing.pdf")
    # Exactly one ERROR record from the helper's logger.
    records = [
        r for r in caplog.records if r.name == "functions.batch_push.blob_fetcher"
    ]
    assert len(records) == 1
    record = records[0]
    assert record.message == "blob download failed"
    assert record.operation == "download_blob"  # type: ignore[attr-defined]
    assert record.container == "docs"  # type: ignore[attr-defined]
    assert record.blob_filename == "missing.pdf"  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_non_azure_exception_is_not_caught() -> None:
    # The helper narrowly catches AzureError; other exceptions must
    # propagate without being logged by this helper.
    class _Boom(Exception):
        pass

    fake = _FakeContainerClient(raises=cast(AzureError, _Boom("nope")))
    with pytest.raises(_Boom):
        await download_blob(_as_container(fake), "x.pdf")
