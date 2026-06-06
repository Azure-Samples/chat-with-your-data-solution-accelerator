"""Search write-side helper for ingestion pipelines.

Pillar: Stable Core
Phase: 6

Provides a thin, typed wrapper over Azure AI Search document upserts
for use by Functions ingestion handlers (`batch_push`, `add_url`,
`search_skill`).
"""

from collections.abc import Mapping, Sequence
from typing import Any, Protocol, runtime_checkable

import logging

from azure.core.exceptions import AzureError

from backend.core.types import SearchDocument


logger = logging.getLogger(__name__)


@runtime_checkable
class SupportsMergeOrUploadDocuments(Protocol):
    """Narrow client protocol for Azure Search write operations.

    Keyword-only ``documents`` is the v2 internal contract. The Azure
    SDK's ``SearchClient.merge_or_upload_documents`` is positional-
    or-keyword (``(self, documents, **kwargs)``) and therefore does
    not satisfy this Protocol structurally -- consumers wrap the SDK
    client in :class:`SearchWriterAdapter` before handing it to
    :func:`push_documents` or to anything else that types its
    write-client parameter as ``SupportsMergeOrUploadDocuments``.

    ``@runtime_checkable`` enables ``isinstance`` checks so tests can
    assert structural satisfaction without having to import the
    concrete adapter class everywhere a Protocol satisfaction proof
    is needed.
    """

    async def merge_or_upload_documents(
        self, *, documents: Sequence[Mapping[str, Any]]
    ) -> list[Any]: ...


class SearchWriterAdapter:
    """Adapter wrapping an Azure SDK ``SearchClient`` for keyword-only writes.

    The Azure SDK's ``SearchClient.merge_or_upload_documents`` is
    positional-or-keyword, so it does not satisfy
    :class:`SupportsMergeOrUploadDocuments` structurally. This thin
    wrapper exposes a keyword-only ``documents`` parameter that
    matches the Protocol and forwards to the SDK using a keyword
    argument (a shape the SDK already accepts).

    The wrapped client is typed ``Any`` because it is a third-party
    SDK object whose shape the boundary deliberately does not narrow
    further (Hard Rule #11(a)). Lifecycle (``__aenter__`` /
    ``__aexit__``) stays owned by the caller -- the adapter is a
    structural shim, not a resource owner.
    """

    def __init__(self, search_client: Any) -> None:
        self._client = search_client

    async def merge_or_upload_documents(
        self, *, documents: Sequence[Mapping[str, Any]]
    ) -> list[Any]:
        return await self._client.merge_or_upload_documents(documents=documents)


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
