"""Tests for the `BaseSearch` ABC default behavior.

Pillar: Stable Core
Phase: 3
"""

from typing import Sequence
from unittest.mock import MagicMock

import inspect
import pytest

from backend.core.providers.search.base import BaseSearch
from backend.core.settings import AppSettings
from backend.core.types import SearchDocument, SearchResult


class _MinimalSearch(BaseSearch):
    """Concrete subclass that overrides only the @abstractmethod members.

    Lets the suite exercise the non-abstract default behavior of
    :meth:`BaseSearch.merge_or_upload_documents` without pulling in a
    real provider's SDK surface.
    """

    async def search(
        self,
        query: str,
        *,
        top_k: int | None = None,
        vector: Sequence[float] | None = None,
        filter_expression: str | None = None,
    ) -> Sequence[SearchResult]:
        return []

    async def delete_by_source(self, source: str) -> int:
        return 0


def _make_settings() -> AppSettings:
    # MagicMock(spec=AppSettings) keeps construction cheap without
    # forcing the env shape the real AppSettings validator wants;
    # BaseSearch only stashes the reference on `self._settings`.
    return MagicMock(spec=AppSettings)


def test_minimal_subclass_instantiates_without_overriding_write_method() -> None:
    """`merge_or_upload_documents` is not @abstractmethod.

    Existing concrete providers (`AzureSearch`, `PgVector`) must keep
    instantiating until each lands its own override; if this test
    fails, the new method became abstract by mistake.
    """
    instance = _MinimalSearch(_make_settings(), MagicMock())
    assert isinstance(instance, BaseSearch)


@pytest.mark.asyncio
async def test_default_merge_or_upload_raises_not_implemented() -> None:
    """Calling the default body raises NotImplementedError with the class name."""
    instance = _MinimalSearch(_make_settings(), MagicMock())
    doc = SearchDocument(id="doc-1", content="hello", title="t.txt")
    with pytest.raises(NotImplementedError) as exc_info:
        await instance.merge_or_upload_documents(documents=[doc])
    assert "_MinimalSearch" in str(exc_info.value)
    assert "merge_or_upload_documents" in str(exc_info.value)


@pytest.mark.asyncio
async def test_default_merge_or_upload_raises_on_empty_input() -> None:
    """Empty input still raises -- the default is not a silent no-op.

    Concrete overrides may short-circuit empty input (e.g. `push_documents`
    in `writer.py` does), but the base default fails loud regardless so
    a missing override never silently drops a partial batch.
    """
    instance = _MinimalSearch(_make_settings(), MagicMock())
    with pytest.raises(NotImplementedError):
        await instance.merge_or_upload_documents(documents=[])


def test_merge_or_upload_signature_is_keyword_only() -> None:
    """`documents` must be keyword-only (matches SupportsMergeOrUploadDocuments)."""
    sig = inspect.signature(BaseSearch.merge_or_upload_documents)
    documents_param = sig.parameters["documents"]
    assert documents_param.kind is inspect.Parameter.KEYWORD_ONLY


@pytest.mark.asyncio
async def test_default_ensure_schema_is_noop() -> None:
    """`ensure_schema` default body returns None without raising.

    Providers whose index is managed out-of-band (Azure Search index
    created by Bicep, future managed-vector services) inherit the
    default and require no override. Callers wire
    `await provider.ensure_schema()` unconditionally; the no-op base
    keeps that callsite provider-agnostic.
    """
    instance = _MinimalSearch(_make_settings(), MagicMock())
    result = await instance.ensure_schema()
    assert result is None


def test_ensure_schema_signature_takes_no_required_args() -> None:
    """`ensure_schema()` must be callable with zero arguments other than self."""
    sig = inspect.signature(BaseSearch.ensure_schema)
    non_self_params = [
        p for name, p in sig.parameters.items() if name != "self"
    ]
    assert non_self_params == [], (
        f"ensure_schema must take no required args beyond self; "
        f"got {[p.name for p in non_self_params]}"
    )
