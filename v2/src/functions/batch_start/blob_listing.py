"""Pillar: Stable Core
Phase: 6 (Functions blueprints / modular RAG indexing pipeline)

Blob listing helper for the ``batch_start`` blueprint.

``batch_start`` needs the set of blob names in a container (optionally
filtered by prefix) so it can fan out one queue message per blob to
``batch_push``. This module owns only the listing call.

Hard Rule #14 (SDK boundary resilience): the SDK boundary is wrapped
per the policy in [v2/docs/exception_handling_policy.md] §"Functions
blueprints" — narrow catch of ``azure.core.exceptions.AzureError``
with structured ``logger.exception`` extras, then re-raise so the
Functions runtime applies its retry / poison-queue semantics.
"""

import logging

from azure.core.exceptions import AzureError
from azure.storage.blob.aio import ContainerClient

logger = logging.getLogger(__name__)


async def list_blobs(
    container_client: ContainerClient,
    prefix: str | None = None,
) -> list[str]:
    """Return blob names in the container (optionally filtered by prefix).

    Caller owns the lifecycle of ``container_client`` (treat it as DI)
    so this helper stays free of credentials wiring. The async
    iterator from ``list_blob_names`` is fully materialized -- the
    handler needs both the count (for the HTTP response) and the names
    (for enqueue) and ingestion fan-out is bounded (typical containers
    have hundreds of blobs, not millions).

    Per [v2/docs/exception_handling_policy.md] §"Functions blueprints":
    catch ``AzureError`` at the SDK boundary, log with structured
    extras (operation, container, prefix), re-raise to escalate to the
    runtime's retry / poison-queue policy.
    """
    try:
        return [
            name
            async for name in container_client.list_blob_names(name_starts_with=prefix)
        ]
    except AzureError:
        logger.exception(
            "blob listing failed",
            extra={
                "operation": "list_blob_names",
                "container": container_client.container_name,
                "prefix": prefix,
            },
        )
        raise
