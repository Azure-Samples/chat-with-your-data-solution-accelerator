"""Tests for ``backend.services.files``."""

import logging
from types import SimpleNamespace as NS
from typing import Any, cast

import pytest
from azure.core.exceptions import AzureError, ResourceNotFoundError
from azure.storage.blob.aio import ContainerClient

import backend.services.files as files_module
from backend.services.files import delete_document, download_document


class _FakeDownloader:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    async def readall(self) -> bytes:
        return self._payload


class _FakeContainerClient:
    """Async stand-in for ``ContainerClient`` used as a context manager.

    Records the construction kwargs and the blob name passed to
    ``download_blob`` so tests can assert the service wired the SDK
    client against the resolved endpoint + container.
    """

    def __init__(
        self,
        *,
        account_url: str,
        container_name: str,
        credential: object,
        payload: bytes = b"",
        raises: BaseException | None = None,
    ) -> None:
        self.account_url = account_url
        self.container_name = container_name
        self.credential = credential
        self._payload = payload
        self._raises = raises
        self.calls: list[str] = []

    async def __aenter__(self) -> "_FakeContainerClient":
        return self

    async def __aexit__(self, *_exc: object) -> bool:
        return False

    async def download_blob(self, blob: str) -> _FakeDownloader:
        self.calls.append(blob)
        if self._raises is not None:
            raise self._raises
        return _FakeDownloader(self._payload)

    async def delete_blob(self, blob: str) -> None:
        self.calls.append(blob)
        if self._raises is not None:
            raise self._raises


def _settings_stub(
    *,
    documents_container: str = "documents",
    storage_account_name: str = "stg",
    storage_blob_endpoint: str = "",
) -> Any:
    return NS(
        storage=NS(
            documents_container=documents_container,
            storage_account_name=storage_account_name,
            storage_blob_endpoint=storage_blob_endpoint,
        )
    )


def _patch_container_client(
    monkeypatch: pytest.MonkeyPatch,
    *,
    payload: bytes = b"",
    raises: BaseException | None = None,
) -> dict[str, Any]:
    """Patch ``files_module.ContainerClient`` with a recording fake.

    Returns a ``captured`` dict that, after the call, holds the
    constructed fake under ``"client"`` and its construction kwargs
    under ``"kwargs"``.
    """
    captured: dict[str, Any] = {}

    def factory(**kwargs: Any) -> ContainerClient:
        client = _FakeContainerClient(payload=payload, raises=raises, **kwargs)
        captured["client"] = client
        captured["kwargs"] = kwargs
        return cast(ContainerClient, client)

    monkeypatch.setattr(files_module, "ContainerClient", factory)
    return captured


@pytest.mark.asyncio
async def test_returns_blob_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = _patch_container_client(monkeypatch, payload=b"%PDF-1.7 hello")

    result = await download_document(
        "Benefit_Options.pdf",
        settings=_settings_stub(),
        credential=cast(Any, object()),
    )

    assert result == b"%PDF-1.7 hello"
    assert captured["client"].calls == ["Benefit_Options.pdf"]


@pytest.mark.asyncio
async def test_constructs_client_against_resolved_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _patch_container_client(monkeypatch, payload=b"x")
    credential = object()

    await download_document(
        "doc.pdf",
        settings=_settings_stub(
            documents_container="docs", storage_account_name="acct"
        ),
        credential=cast(Any, credential),
    )

    kwargs = captured["kwargs"]
    assert kwargs["account_url"] == "https://acct.blob.core.windows.net"
    assert kwargs["container_name"] == "docs"
    assert kwargs["credential"] is credential


@pytest.mark.asyncio
async def test_missing_blob_raises_file_not_found_without_error_log(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _patch_container_client(monkeypatch, raises=ResourceNotFoundError("not found"))
    caplog.set_level(logging.ERROR, logger="backend.services.files")

    with pytest.raises(FileNotFoundError):
        await download_document(
            "missing.pdf",
            settings=_settings_stub(),
            credential=cast(Any, object()),
        )

    # A 404 is an expected input, not a server error -- nothing logged.
    assert [r for r in caplog.records if r.name == "backend.services.files"] == []


@pytest.mark.asyncio
async def test_other_azure_error_is_logged_and_reraised(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _patch_container_client(monkeypatch, raises=AzureError("boom"))
    caplog.set_level(logging.ERROR, logger="backend.services.files")

    with pytest.raises(AzureError):
        await download_document(
            "report.pdf",
            settings=_settings_stub(documents_container="docs"),
            credential=cast(Any, object()),
        )

    records = [r for r in caplog.records if r.name == "backend.services.files"]
    assert len(records) == 1
    record = records[0]
    assert record.message == "document download failed"
    assert record.operation == "download_document"  # type: ignore[attr-defined]
    assert record.container == "docs"  # type: ignore[attr-defined]
    assert record.blob_filename == "report.pdf"  # type: ignore[attr-defined]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad",
    [
        "",
        "a" * 256,
        "sub/dir.pdf",
        "back\\slash.pdf",
        "../escape.pdf",
        "..",
        "ctrl\x00null.pdf",
        "tab\tchar.pdf",
    ],
)
async def test_invalid_filename_raises_value_error_before_any_sdk_call(
    monkeypatch: pytest.MonkeyPatch, bad: str
) -> None:
    captured = _patch_container_client(monkeypatch, payload=b"x")

    with pytest.raises(ValueError):
        await download_document(
            bad,
            settings=_settings_stub(),
            credential=cast(Any, object()),
        )

    # Validation short-circuits before constructing any SDK client.
    assert "client" not in captured


@pytest.mark.asyncio
async def test_valid_filename_with_spaces_is_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _patch_container_client(monkeypatch, payload=b"ok")

    result = await download_document(
        "Employee Handbook.pdf",
        settings=_settings_stub(),
        credential=cast(Any, object()),
    )

    assert result == b"ok"
    assert captured["client"].calls == ["Employee Handbook.pdf"]


# ---------------------------------------------------------------------------
# delete_document -- blob delete behind the admin document delete
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_returns_true_when_blob_deleted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _patch_container_client(monkeypatch)

    result = await delete_document(
        "Benefit_Options.pdf",
        settings=_settings_stub(documents_container="docs"),
        credential=cast(Any, object()),
    )

    assert result is True
    assert captured["client"].calls == ["Benefit_Options.pdf"]
    assert captured["kwargs"]["container_name"] == "docs"


@pytest.mark.asyncio
async def test_delete_returns_false_when_blob_missing(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _patch_container_client(monkeypatch, raises=ResourceNotFoundError("gone"))
    caplog.set_level(logging.ERROR, logger="backend.services.files")

    result = await delete_document(
        "already_gone.pdf",
        settings=_settings_stub(),
        credential=cast(Any, object()),
    )

    # Idempotent no-op success -- nothing removed, nothing logged.
    assert result is False
    assert [r for r in caplog.records if r.name == "backend.services.files"] == []


@pytest.mark.asyncio
async def test_delete_other_azure_error_is_logged_and_reraised(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _patch_container_client(monkeypatch, raises=AzureError("boom"))
    caplog.set_level(logging.ERROR, logger="backend.services.files")

    with pytest.raises(AzureError):
        await delete_document(
            "report.pdf",
            settings=_settings_stub(documents_container="docs"),
            credential=cast(Any, object()),
        )

    records = [r for r in caplog.records if r.name == "backend.services.files"]
    assert len(records) == 1
    record = records[0]
    assert record.message == "document delete failed"
    assert record.operation == "delete_document"  # type: ignore[attr-defined]
    assert record.container == "docs"  # type: ignore[attr-defined]
    assert record.blob_filename == "report.pdf"  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_delete_rejects_url_typed_source_before_any_sdk_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _patch_container_client(monkeypatch)

    with pytest.raises(ValueError):
        await delete_document(
            "https://example.com/report.pdf",
            settings=_settings_stub(),
            credential=cast(Any, object()),
        )

    # A URL source carries path separators -> rejected before any SDK
    # client is constructed (URLs have no blob to delete).
    assert "client" not in captured
