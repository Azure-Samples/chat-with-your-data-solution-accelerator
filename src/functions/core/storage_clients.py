"""Async context manager that yields the (ContainerClient, QueueClient) pair.

Functions-only helper that owns the nested ``async with
(ContainerClient(...), QueueClient(...))`` boilerplate previously
inlined in every blueprint's ``_execute``. Centralizing it here means:

* every blueprint constructs the SDK client pair with identical
  argument shape (no per-route drift on ``account_url`` vs
  ``account_endpoint`` or ``container_name`` vs ``container``);
* cleanup is guaranteed by the single ``async with`` -- both clients
  close even when one raises during enter/exit;
* the seam to fake in tests collapses from "patch two SDK classes" to
  "patch one context manager".

The helper deliberately does **not** acquire the credential -- callers
build one via the ``backend.core.providers.credentials`` registry
(Hard Rule #4) and pass the already-entered ``credential`` token here. That
keeps this module dependency-light (no registry import) and pure SDK
wiring, mirroring how :func:`functions.core.storage_endpoints.resolve_storage_endpoints`
stays free of settings-construction logic.

Lives under ``functions/core/`` because both consumers
(:mod:`azure.storage.blob.aio` + :mod:`azure.storage.queue.aio`) and
the call sites (Functions blueprints) are Functions-runtime concerns;
the backend FastAPI app never opens these clients.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from azure.core.credentials_async import AsyncTokenCredential
from azure.storage.blob.aio import ContainerClient
from azure.storage.queue.aio import QueueClient


@asynccontextmanager
async def storage_clients(
    *,
    credential: AsyncTokenCredential,
    blob_endpoint: str,
    queue_endpoint: str,
    container_name: str,
    queue_name: str,
) -> AsyncGenerator[tuple[ContainerClient, QueueClient]]:
    """Yield ``(container_client, queue_client)`` for the duration of the block.

    Both clients are constructed against ``credential`` (typically the
    already-entered token from
    ``await cred_provider.get_credential().__aenter__()``) and closed
    in a single ``async with`` so partial-failure cleanup is correct.
    """
    async with (
        ContainerClient(
            account_url=blob_endpoint,
            container_name=container_name,
            credential=credential,
        ) as container_client,
        QueueClient(
            account_url=queue_endpoint,
            queue_name=queue_name,
            credential=credential,
        ) as queue_client,
    ):
        yield container_client, queue_client
