"""Tests for the search write-side helper (Phase 6 task #41, U8g).

Pillar: Stable Core
Phase: 6
"""

from collections.abc import Mapping, Sequence
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from azure.core.exceptions import ServiceRequestError

from backend.core.providers.search.writer import push_documents


@pytest.mark.asyncio
async def test_push_documents_calls_merge_or_upload_with_payload() -> None:
    client = MagicMock()
    client.merge_or_upload_documents = AsyncMock(return_value=[{"key": "a", "succeeded": True}])
    docs: list[Mapping[str, Any]] = [
        {"id": "a", "content": "hello", "content_vector": [0.1, 0.2]},
        {"id": "b", "content": "world", "content_vector": [0.3, 0.4]},
    ]

    result = await push_documents(client, docs)

    client.merge_or_upload_documents.assert_awaited_once_with(documents=docs)
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
    docs: Sequence[Mapping[str, Any]] = [{"id": "a", "content": "hello"}]

    with pytest.raises(ServiceRequestError, match="search unavailable"):
        await push_documents(client, docs)
