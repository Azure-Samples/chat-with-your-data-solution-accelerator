"""Tests for the ``/api/files`` router.

Self-contained: builds a minimal FastAPI app from just the files
router so the test does not depend on the full app wiring.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from azure.core.exceptions import AzureError
from fastapi import FastAPI

from backend.dependencies import get_app_settings, get_credential
from backend.exception_handlers import install_exception_handlers
from backend.routers import files as files_router


def _settings_with_storage(*, documents_container: str = "documents") -> Any:
    settings = MagicMock()
    settings.storage.documents_container = documents_container
    return settings


def _build_app(settings: Any) -> FastAPI:
    app = FastAPI()
    app.include_router(files_router.router)
    install_exception_handlers(app)
    app.dependency_overrides[get_app_settings] = lambda: settings
    app.dependency_overrides[get_credential] = lambda: AsyncMock()
    return app


def _client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


async def test_returns_blob_inline_with_pdf_content_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_download = AsyncMock(return_value=b"%PDF-1.7 hello")
    monkeypatch.setattr(files_router, "download_document", fake_download)

    app = _build_app(_settings_with_storage())
    async with _client(app) as client:
        resp = await client.get("/api/files/Benefit_Options.pdf")

    assert resp.status_code == 200
    assert resp.content == b"%PDF-1.7 hello"
    assert resp.headers["content-type"].startswith("application/pdf")
    assert (
        resp.headers["content-disposition"] == 'inline; filename="Benefit_Options.pdf"'
    )
    # The service is invoked with the decoded filename + injected deps.
    assert fake_download.await_count == 1
    assert fake_download.await_args.args == ("Benefit_Options.pdf",)
    assert "settings" in fake_download.await_args.kwargs
    assert "credential" in fake_download.await_args.kwargs


async def test_guesses_image_content_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        files_router, "download_document", AsyncMock(return_value=b"PNGDATA")
    )
    app = _build_app(_settings_with_storage())
    async with _client(app) as client:
        resp = await client.get("/api/files/diagram.png")

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/png")


async def test_unknown_extension_falls_back_to_octet_stream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        files_router, "download_document", AsyncMock(return_value=b"raw")
    )
    app = _build_app(_settings_with_storage())
    async with _client(app) as client:
        resp = await client.get("/api/files/archive.unknownext")

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/octet-stream")


async def test_decodes_spaces_in_filename(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_download = AsyncMock(return_value=b"ok")
    monkeypatch.setattr(files_router, "download_document", fake_download)

    app = _build_app(_settings_with_storage())
    async with _client(app) as client:
        resp = await client.get("/api/files/Employee%20Handbook.pdf")

    assert resp.status_code == 200
    assert fake_download.await_args.args == ("Employee Handbook.pdf",)


async def test_malformed_filename_returns_400(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        files_router,
        "download_document",
        AsyncMock(side_effect=ValueError("filename must not contain path separators.")),
    )
    app = _build_app(_settings_with_storage())
    async with _client(app) as client:
        resp = await client.get("/api/files/whatever.pdf")

    assert resp.status_code == 400


async def test_missing_blob_returns_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        files_router,
        "download_document",
        AsyncMock(side_effect=FileNotFoundError("missing.pdf")),
    )
    app = _build_app(_settings_with_storage())
    async with _client(app) as client:
        resp = await client.get("/api/files/missing.pdf")

    assert resp.status_code == 404


async def test_unconfigured_storage_returns_503_without_calling_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_download = AsyncMock(return_value=b"never")
    monkeypatch.setattr(files_router, "download_document", fake_download)

    app = _build_app(_settings_with_storage(documents_container=""))
    async with _client(app) as client:
        resp = await client.get("/api/files/doc.pdf")

    assert resp.status_code == 503
    fake_download.assert_not_awaited()


async def test_azure_error_propagates_to_app_handler_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        files_router,
        "download_document",
        AsyncMock(side_effect=AzureError("storage exploded")),
    )
    app = _build_app(_settings_with_storage())
    async with _client(app) as client:
        resp = await client.get("/api/files/doc.pdf")

    assert resp.status_code == 503
