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

from backend.core.types import SearchDocument


logger = logging.getLogger(__name__)


class SupportsMergeOrUploadDocuments(Protocol):
    """Narrow client protocol for Azure Search write operations.

    The Azure SDK contract is ``Sequence[Mapping[str, Any]]`` -- a
    deliberate boundary expressed in the SDK's own type stubs. This
    Protocol stays in lockstep with the SDK so we don't accidentally
    over-constrain the third-party shape (Hard Rule #11(a)
    boundary).
    """

    async def merge_or_upload_documents(
        self, *, documents: Sequence[Mapping[str, Any]]
    ) -> list[Any]: ...


async def push_documents(
    search_client: SupportsMergeOrUploadDocuments,
    docs: Sequence[SearchDocument],
) -> list[Any]:
    """Upsert ingestion documents into the configured search index.

    Accepts a sequence of :class:`SearchDocument` (Hard Rule #15: the
    ingestion wire shape is a typed model, not a free-form dict).
    Converts to the SDK's ``Mapping[str, Any]`` shape here -- the
    single ``model_dump()`` call IS the SDK boundary the rule
    prescribes. Empty inputs return early and do not call the
    underlying SDK.
    """
    if not docs:
        return []

    payload: list[dict[str, Any]] = [d.model_dump() for d in docs]
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
