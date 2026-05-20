"""Pillar: Stable Core / Phase: 6 — tests for functions/core/storage_clients.py."""

from typing import Any
from unittest.mock import patch

import pytest
from azure.storage.blob.aio import ContainerClient
from azure.storage.queue.aio import QueueClient

from functions.core.storage_clients import storage_clients


class _FakeCredential:
    """Stand-in for an entered AsyncTokenCredential (SDK only inspects calls)."""

    async def get_token(self, *scopes: str, **_: Any) -> Any:  # pragma: no cover - unused
        raise AssertionError("storage_clients should not request tokens itself")

    async def close(self) -> None:  # pragma: no cover - unused
        return None


@pytest.mark.asyncio
async def test_storage_clients_yields_container_and_queue_client_pair() -> None:
    cred = _FakeCredential()
    async with storage_clients(
        credential=cred,  # type: ignore[arg-type]
        blob_endpoint="https://acct.blob.core.windows.net",
        queue_endpoint="https://acct.queue.core.windows.net",
        container_name="documents",
        queue_name="doc-processing",
    ) as (container, queue):
        assert isinstance(container, ContainerClient)
        assert isinstance(queue, QueueClient)


@pytest.mark.asyncio
async def test_storage_clients_passes_endpoints_and_names_to_sdk_constructors() -> None:
    cred = _FakeCredential()

    captured: dict[str, dict[str, object]] = {}

    real_container_init = ContainerClient.__init__
    real_queue_init = QueueClient.__init__

    def _spy_container(self: ContainerClient, *args: object, **kwargs: object) -> None:
        captured["container"] = dict(kwargs)
        real_container_init(self, *args, **kwargs)

    def _spy_queue(self: QueueClient, *args: object, **kwargs: object) -> None:
        captured["queue"] = dict(kwargs)
        real_queue_init(self, *args, **kwargs)

    with (
        patch.object(ContainerClient, "__init__", _spy_container),
        patch.object(QueueClient, "__init__", _spy_queue),
    ):
        async with storage_clients(
            credential=cred,  # type: ignore[arg-type]
            blob_endpoint="https://acct.blob.core.windows.net",
            queue_endpoint="https://acct.queue.core.windows.net",
            container_name="documents",
            queue_name="doc-processing",
        ):
            pass

    assert captured["container"]["account_url"] == "https://acct.blob.core.windows.net"
    assert captured["container"]["container_name"] == "documents"
    assert captured["container"]["credential"] is cred
    assert captured["queue"]["account_url"] == "https://acct.queue.core.windows.net"
    assert captured["queue"]["queue_name"] == "doc-processing"
    assert captured["queue"]["credential"] is cred


@pytest.mark.asyncio
async def test_storage_clients_propagates_exception_raised_inside_block() -> None:
    # Cleanup happens via the inner `async with` (SDK contract). All this
    # helper owns is correct re-raise -- verify the exception isn't swallowed.
    cred = _FakeCredential()
    with pytest.raises(RuntimeError, match="boom"):
        async with storage_clients(
            credential=cred,  # type: ignore[arg-type]
            blob_endpoint="https://acct.blob.core.windows.net",
            queue_endpoint="https://acct.queue.core.windows.net",
            container_name="documents",
            queue_name="doc-processing",
        ):
            raise RuntimeError("boom")


@pytest.mark.asyncio
async def test_storage_clients_yielded_value_is_a_two_tuple() -> None:
    # Shape sanity: blueprint _execute destructures `as (container, queue)`.
    cred = _FakeCredential()
    async with storage_clients(
        credential=cred,  # type: ignore[arg-type]
        blob_endpoint="https://acct.blob.core.windows.net",
        queue_endpoint="https://acct.queue.core.windows.net",
        container_name="documents",
        queue_name="doc-processing",
    ) as yielded:
        assert isinstance(yielded, tuple)
        assert len(yielded) == 2
