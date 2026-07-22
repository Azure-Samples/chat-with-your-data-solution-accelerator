"""Storage endpoint URL resolution for Functions blueprints.

Functions-only helper that derives ``(blob_endpoint, queue_endpoint)``
URLs from :class:`StorageSettings`. Lives under ``functions/core/``
because backend code never instantiates Blob or Queue SDK clients --
only the Functions runtime does -- so this is plumbing local to the
ingestion pipeline per
[.github/instructions/v2-functions-core.instructions.md] "Functions-
runtime helper" rule.

Extracted from ``batch_start/blueprint._resolve_endpoints`` so every
blueprint that talks to Blob + Queue (``batch_start``, ``batch_push``,
``add_url``) can call the same single source of truth instead of
duplicating the ``.blob. -> .queue.`` swap. Pure function, no I/O, no
SDK imports -- trivially unit-testable without Azurite.
"""

from backend.core.settings import StorageSettings


def resolve_storage_endpoints(storage: StorageSettings) -> tuple[str, str]:
    """Return ``(blob_endpoint, queue_endpoint)`` URLs.

    Prefers the explicit ``AZURE_STORAGE_BLOB_ENDPOINT`` when set
    (sovereign-cloud safe); otherwise derives the public-cloud URL
    from ``AZURE_STORAGE_ACCOUNT_NAME``. Queue endpoint is derived
    from the blob endpoint by swapping the service segment so both
    services share one DNS suffix in any cloud.

    Raises:
        ValueError: if neither ``storage_blob_endpoint`` nor
            ``storage_account_name`` is configured -- there is no way
            to derive a URL and the caller would otherwise build
            ``https://.blob.core.windows.net`` (always 404).
    """
    blob_endpoint = storage.storage_blob_endpoint or (
        f"https://{storage.storage_account_name}.blob.core.windows.net"
        if storage.storage_account_name
        else ""
    )
    if not blob_endpoint:
        raise ValueError(
            "Cannot resolve storage endpoints: both "
            "AZURE_STORAGE_BLOB_ENDPOINT and AZURE_STORAGE_ACCOUNT_NAME are empty."
        )
    queue_endpoint = blob_endpoint.replace(".blob.", ".queue.", 1)
    return blob_endpoint, queue_endpoint
