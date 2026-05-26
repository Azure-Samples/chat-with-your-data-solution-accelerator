"""Search write-side helper for ingestion pipelines.

Pillar: Stable Core
Phase: 6

Provides a thin, typed wrapper over Azure AI Search document upserts
for use by Functions ingestion handlers (`batch_push`, `add_url`,
`search_skill`).
"""

from collections.abc import Mapping, Sequence
from typing import Any, Protocol

import logging

from azure.core.exceptions import AzureError


logger = logging.getLogger(__name__)


class SupportsMergeOrUploadDocuments(Protocol):
    """Narrow client protocol for Azure Search write operations."""

    async def merge_or_upload_documents(
        self, *, documents: Sequence[Mapping[str, Any]]
    ) -> list[Any]: ...


async def push_documents(
    search_client: SupportsMergeOrUploadDocuments,
    docs: Sequence[Mapping[str, Any]],
) -> list[Any]:
    """Upsert ingestion documents into the configured search index.

    Empty inputs return early and do not call the underlying SDK.
    """
    if not docs:
        return []

    payload = list(docs)
    try:
        return await search_client.merge_or_upload_documents(documents=payload)
    except AzureError:
        logger.exception(
            "search writer merge_or_upload_documents failed",
            extra={
                "operation": "push_documents",
                "provider": "search_writer",
                "document_count": len(payload),
            },
        )
        raise
