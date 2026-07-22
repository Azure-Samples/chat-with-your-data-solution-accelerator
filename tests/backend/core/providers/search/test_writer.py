"""Tests for the search write-side helper."""

from collections.abc import Sequence
from unittest.mock import AsyncMock, MagicMock

import pytest
from azure.core.exceptions import ServiceRequestError

from backend.core.providers.search.writer import (
    SearchWriterAdapter,
    SupportsMergeOrUploadDocuments,
    push_documents,
)
from backend.core.types import SearchDocument


@pytest.mark.asyncio
async def test_push_documents_calls_merge_or_upload_with_payload() -> None:
    client = MagicMock()
    client.merge_or_upload_documents = AsyncMock(
        return_value=[{"key": "a", "succeeded": True}]
    )
    docs = [
        SearchDocument(id="a", content="hello", content_vector=[0.1, 0.2]),
        SearchDocument(id="b", content="world", content_vector=[0.3, 0.4]),
    ]

    result = await push_documents(client, docs)

    client.merge_or_upload_documents.assert_awaited_once_with(
        documents=[d.model_dump() for d in docs]
    )
    assert result == [{"key": "a", "succeeded": True}]


@pytest.mark.asyncio
async def test_push_documents_returns_empty_list_when_docs_empty() -> None:
    client = MagicMock()
    client.merge_or_upload_documents = AsyncMock()

    result = await push_documents(client, [])

    assert result == []
    client.merge_or_upload_documents.assert_not_called()


@pytest.mark.asyncio
async def test_push_documents_reraises_azure_errors() -> None:
    client = MagicMock()
    client.merge_or_upload_documents = AsyncMock(
        side_effect=ServiceRequestError("search unavailable")
    )
    docs: Sequence[SearchDocument] = [SearchDocument(id="a", content="hello")]

    with pytest.raises(ServiceRequestError, match="search unavailable"):
        await push_documents(client, docs)


def test_search_writer_adapter_satisfies_protocol_runtime_check() -> None:
    """Adapter satisfies SupportsMergeOrUploadDocuments structurally.

    Proves the adapter exists for its sole purpose -- to be the
    structural bridge between the SDK's positional-or-keyword
    ``merge_or_upload_documents`` and the v2 internal keyword-only
    Protocol. ``runtime_checkable`` enables ``isinstance``.
    """
    sdk_like_client = MagicMock()
    sdk_like_client.merge_or_upload_documents = AsyncMock(return_value=[])

    adapter = SearchWriterAdapter(sdk_like_client)

    assert isinstance(adapter, SupportsMergeOrUploadDocuments)


@pytest.mark.asyncio
async def test_search_writer_adapter_delegates_to_wrapped_client_with_kwarg() -> None:
    """Adapter forwards ``documents`` to the wrapped SDK client as kwarg.

    The wrapped SDK accepts both positional and keyword ``documents``;
    the adapter forwards by keyword so the call site exactly matches
    the keyword-only Protocol surface on both sides of the boundary.
    """
    sdk_like_client = MagicMock()
    sdk_like_client.merge_or_upload_documents = AsyncMock(
        return_value=[{"key": "x", "succeeded": True}]
    )
    payload = [{"id": "x", "content": "hello"}]

    adapter = SearchWriterAdapter(sdk_like_client)
    result = await adapter.merge_or_upload_documents(documents=payload)

    sdk_like_client.merge_or_upload_documents.assert_awaited_once_with(
        documents=payload
    )
    assert result == [{"key": "x", "succeeded": True}]


@pytest.mark.asyncio
async def test_push_documents_works_with_search_writer_adapter() -> None:
    """End-to-end shape: ``push_documents`` accepts the adapter and writes correctly.

    Proves the adapter satisfies the ``push_documents`` parameter
    type at runtime AND that the SDK boundary still receives the
    expected ``Sequence[Mapping[str, Any]]`` wire shape from
    :meth:`SearchDocument.model_dump`.
    """
    sdk_like_client = MagicMock()
    sdk_like_client.merge_or_upload_documents = AsyncMock(
        return_value=[{"succeeded": True}]
    )
    adapter = SearchWriterAdapter(sdk_like_client)
    docs = [SearchDocument(id="a", content="hello", content_vector=[0.1, 0.2])]

    result = await push_documents(adapter, docs)

    sdk_like_client.merge_or_upload_documents.assert_awaited_once_with(
        documents=[docs[0].model_dump()]
    )
    assert result == [{"succeeded": True}]


@pytest.mark.asyncio
async def test_search_writer_adapter_propagates_sdk_exceptions() -> None:
    """SDK errors bubble through the adapter unchanged.

    The adapter is a structural shim and owns no retry / mapping
    logic; ``push_documents`` is the layer that logs + re-raises.
    This test pins the adapter's behavior so a future change can't
    silently swallow SDK failures.
    """
    sdk_like_client = MagicMock()
    sdk_like_client.merge_or_upload_documents = AsyncMock(
        side_effect=ServiceRequestError("transient")
    )
    adapter = SearchWriterAdapter(sdk_like_client)

    with pytest.raises(ServiceRequestError, match="transient"):
        await adapter.merge_or_upload_documents(documents=[{"id": "a"}])
