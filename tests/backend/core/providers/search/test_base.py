"""Tests for the `BaseSearch` ABC default behavior."""

from typing import Sequence
from unittest.mock import MagicMock

import inspect
import pytest
from pydantic import ValidationError

from backend.core.providers.search.base import BaseSearch, SourceListing
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
    non_self_params = [p for name, p in sig.parameters.items() if name != "self"]
    assert non_self_params == [], (
        f"ensure_schema must take no required args beyond self; "
        f"got {[p.name for p in non_self_params]}"
    )


def test_source_listing_is_frozen() -> None:
    """`SourceListing` is immutable per Pydantic v2 frozen config."""
    listing = SourceListing(
        source="contract.pdf",
        chunk_count=3,
        last_modified="2026-01-01T00:00:00Z",
    )
    with pytest.raises(ValidationError):
        listing.source = "other.pdf"  # type: ignore[misc]


def test_source_listing_forbids_extra_fields() -> None:
    """Unknown keys raise `ValidationError` per `extra="forbid"`."""
    with pytest.raises(ValidationError):
        SourceListing.model_validate(
            {
                "source": "a.pdf",
                "chunk_count": 1,
                "last_modified": None,
                "foo": "bar",
            }
        )


def test_source_listing_last_modified_optional_defaults_none() -> None:
    """`last_modified` defaults to ``None`` when omitted."""
    listing = SourceListing(source="a.pdf", chunk_count=0)
    assert listing.last_modified is None


def test_source_listing_round_trip_via_model_dump_and_validate() -> None:
    """`model_validate(model_dump())` is the identity for `SourceListing`."""
    original = SourceListing(
        source="contract.pdf",
        chunk_count=7,
        last_modified="2026-05-31T12:34:56Z",
    )
    rebuilt = SourceListing.model_validate(original.model_dump())
    assert rebuilt == original


def test_source_listing_requires_source_and_chunk_count() -> None:
    """Omitting either required field raises `ValidationError`."""
    with pytest.raises(ValidationError):
        SourceListing.model_validate({"chunk_count": 1})
    with pytest.raises(ValidationError):
        SourceListing.model_validate({"source": "a.pdf"})


@pytest.mark.asyncio
async def test_default_list_sources_raises_not_implemented() -> None:
    """Calling the default body raises NotImplementedError with the class name.

    Mirrors the fail-loud contract of
    :meth:`BaseSearch.merge_or_upload_documents` -- a provider that
    forgets to override fails at the admin route call site rather
    than silently returning an empty list.
    """
    instance = _MinimalSearch(_make_settings(), MagicMock())
    with pytest.raises(NotImplementedError) as exc_info:
        await instance.list_sources()
    assert "_MinimalSearch" in str(exc_info.value)
    assert "list_sources" in str(exc_info.value)


def test_list_sources_signature_takes_no_required_args() -> None:
    """`list_sources()` must be callable with zero arguments other than self."""
    sig = inspect.signature(BaseSearch.list_sources)
    non_self_params = [p for name, p in sig.parameters.items() if name != "self"]
    assert non_self_params == [], (
        f"list_sources must take no required args beyond self; "
        f"got {[p.name for p in non_self_params]}"
    )


def test_list_sources_is_not_abstract() -> None:
    """`list_sources` ships with a default body, not as @abstractmethod.

    The default raises NotImplementedError so existing providers
    that have not yet landed their override still instantiate (their
    other abstract methods stay enforced). If this test fails, the
    method became abstract by mistake and breaks `AzureSearch` /
    `PgVector` construction.
    """
    assert "list_sources" not in BaseSearch.__abstractmethods__


@pytest.mark.asyncio
async def test_default_get_document_by_key_raises_not_implemented() -> None:
    """Calling the default body raises NotImplementedError with the class name.

    Mirrors the fail-loud contract of
    :meth:`BaseSearch.list_sources` -- a provider that forgets to
    override fails at the call site rather than silently skipping
    citation enrichment.
    """
    instance = _MinimalSearch(_make_settings(), MagicMock())
    with pytest.raises(NotImplementedError) as exc_info:
        await instance.get_document_by_key("doc-1")
    assert "_MinimalSearch" in str(exc_info.value)
    assert "get_document_by_key" in str(exc_info.value)


def test_get_document_by_key_is_not_abstract() -> None:
    """`get_document_by_key` ships with a default body, not @abstractmethod.

    The default raises NotImplementedError so existing providers that
    have not yet landed their override still instantiate. If this test
    fails, the method became abstract by mistake and breaks
    `AzureSearch` / `PgVector` construction.
    """
    assert "get_document_by_key" not in BaseSearch.__abstractmethods__
