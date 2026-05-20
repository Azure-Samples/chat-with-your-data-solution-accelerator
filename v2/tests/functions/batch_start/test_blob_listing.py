"""Pillar: Stable Core / Phase: 6 — tests for v2/src/functions/batch_start/blob_listing.py."""

import logging
from collections.abc import AsyncIterator
from typing import cast

import pytest
from azure.core.exceptions import AzureError
from azure.storage.blob.aio import ContainerClient

from functions.batch_start.blob_listing import list_blobs


class _FakeContainerClient:
    """Minimal async stand-in for ``azure.storage.blob.aio.ContainerClient``.

    Only the two attrs/methods touched by ``list_blobs`` are modeled:
    ``container_name`` (used in the error log) and
    ``list_blob_names(name_starts_with=...)`` (the SDK call).
    """

    def __init__(
        self,
        names: list[str],
        *,
        container_name: str = "documents",
        raises: AzureError | None = None,
    ) -> None:
        self.container_name = container_name
        self._names = names
        self._raises = raises
        self.last_prefix: str | None = "<<unset>>"  # sentinel — replaced on first call

    def list_blob_names(self, *, name_starts_with: str | None = None) -> AsyncIterator[str]:
        self.last_prefix = name_starts_with
        if self._raises is not None:
            raise self._raises
        return self._aiter(self._names)

    @staticmethod
    async def _aiter(names: list[str]) -> AsyncIterator[str]:
        for n in names:
            yield n


def _as_container(fake: _FakeContainerClient) -> ContainerClient:
    """Structural cast so pyright treats the fake as a real ContainerClient."""
    return cast(ContainerClient, fake)


@pytest.mark.asyncio
async def test_returns_all_blob_names() -> None:
    fake = _FakeContainerClient(["a.pdf", "b.docx", "c.txt"])
    result = await list_blobs(_as_container(fake))
    assert result == ["a.pdf", "b.docx", "c.txt"]


@pytest.mark.asyncio
async def test_prefix_is_forwarded_to_sdk() -> None:
    fake = _FakeContainerClient(["2026/x.pdf"])
    await list_blobs(_as_container(fake), prefix="2026/")
    assert fake.last_prefix == "2026/"


@pytest.mark.asyncio
async def test_prefix_none_by_default_passes_none_to_sdk() -> None:
    fake = _FakeContainerClient(["x.pdf"])
    await list_blobs(_as_container(fake))
    assert fake.last_prefix is None


@pytest.mark.asyncio
async def test_empty_container_returns_empty_list() -> None:
    fake = _FakeContainerClient([])
    result = await list_blobs(_as_container(fake))
    assert result == []


@pytest.mark.asyncio
async def test_azure_error_is_logged_and_reraised(
    caplog: pytest.LogCaptureFixture,
) -> None:
    fake = _FakeContainerClient(
        [], container_name="documents", raises=AzureError("boom")
    )
    caplog.set_level(logging.ERROR, logger="functions.batch_start.blob_listing")
    with pytest.raises(AzureError):
        await list_blobs(_as_container(fake), prefix="2026/")
    # Structured log fired with operation + container + prefix in extras.
    record = next(r for r in caplog.records if r.message == "blob listing failed")
    assert record.levelno == logging.ERROR
    assert record.operation == "list_blob_names"  # type: ignore[attr-defined]
    assert record.container == "documents"  # type: ignore[attr-defined]
    assert record.prefix == "2026/"  # type: ignore[attr-defined]
