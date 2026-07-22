"""Tests for src/functions/add_url/url_fetcher.py."""

import logging

import httpx
import pytest

import functions.add_url.url_fetcher as module_under_test
from functions.add_url.url_fetcher import fetch_url


def _mock_client(handler: object) -> httpx.AsyncClient:
    """Build an ``httpx.AsyncClient`` backed by ``httpx.MockTransport(handler)``."""
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))  # type: ignore[arg-type]


@pytest.fixture(autouse=True)
def _bypass_ssrf_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch out the SSRF DNS check so tests can use .invalid hostnames.

    Tests in this file exercise HTTP behavior (status codes, error handling,
    body decoding) via ``httpx.MockTransport`` — they are not testing SSRF
    protection. Bypassing ``_validate_public_http_url`` prevents
    ``socket.getaddrinfo`` from failing on ``.invalid`` TLD domains that are
    intentionally unresolvable (RFC 6761).
    """
    monkeypatch.setattr(
        module_under_test, "_validate_public_http_url", lambda _url: None
    )


@pytest.mark.asyncio
async def test_returns_response_bytes_on_2xx() -> None:
    expected_body = b"<html>hello world</html>"

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://example.invalid/page"
        return httpx.Response(200, content=expected_body)

    async with _mock_client(handler) as client:
        result = await fetch_url("https://example.invalid/page", client=client)
    assert result == expected_body


@pytest.mark.asyncio
async def test_empty_response_body_returns_empty_bytes() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"")

    async with _mock_client(handler) as client:
        result = await fetch_url("https://example.invalid/empty", client=client)
    assert result == b""


@pytest.mark.asyncio
async def test_4xx_status_is_logged_and_reraised(
    caplog: pytest.LogCaptureFixture,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, content=b"not found")

    caplog.set_level(logging.ERROR, logger="functions.add_url.url_fetcher")
    async with _mock_client(handler) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await fetch_url("https://example.invalid/missing", client=client)

    records = [r for r in caplog.records if r.name == "functions.add_url.url_fetcher"]
    assert len(records) == 1
    record = records[0]
    assert record.message == "url fetch failed"
    assert record.operation == "fetch_url"  # type: ignore[attr-defined]
    assert record.provider == "httpx"  # type: ignore[attr-defined]
    assert record.url == "https://example.invalid/missing"  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_5xx_status_is_logged_and_reraised(
    caplog: pytest.LogCaptureFixture,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, content=b"")

    caplog.set_level(logging.ERROR, logger="functions.add_url.url_fetcher")
    async with _mock_client(handler) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await fetch_url("https://example.invalid/down", client=client)

    records = [r for r in caplog.records if r.name == "functions.add_url.url_fetcher"]
    assert len(records) == 1
    assert records[0].operation == "fetch_url"  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_connect_error_is_logged_and_reraised(
    caplog: pytest.LogCaptureFixture,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("name resolution failed")

    caplog.set_level(logging.ERROR, logger="functions.add_url.url_fetcher")
    async with _mock_client(handler) as client:
        with pytest.raises(httpx.ConnectError):
            await fetch_url("https://example.invalid/", client=client)

    records = [r for r in caplog.records if r.name == "functions.add_url.url_fetcher"]
    assert len(records) == 1
    assert records[0].message == "url fetch failed"
    assert records[0].operation == "fetch_url"  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_timeout_is_logged_and_reraised(
    caplog: pytest.LogCaptureFixture,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("read timeout", request=request)

    caplog.set_level(logging.ERROR, logger="functions.add_url.url_fetcher")
    async with _mock_client(handler) as client:
        with pytest.raises(httpx.ReadTimeout):
            await fetch_url("https://example.invalid/slow", client=client)

    records = [r for r in caplog.records if r.name == "functions.add_url.url_fetcher"]
    assert len(records) == 1
    assert records[0].operation == "fetch_url"  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_non_httpx_exception_is_not_caught() -> None:
    # The helper narrowly catches httpx.HTTPError; other exceptions
    # must propagate without being logged by this helper.
    class _Boom(Exception):
        pass

    def handler(request: httpx.Request) -> httpx.Response:
        raise _Boom("nope")

    async with _mock_client(handler) as client:
        with pytest.raises(_Boom):
            await fetch_url("https://example.invalid/", client=client)


@pytest.mark.asyncio
async def test_default_client_branch_is_exercised() -> None:
    # When no client is injected, fetch_url constructs its own
    # ``httpx.AsyncClient`` with ``follow_redirects=True`` and the
    # default timeout. Verify the implicit-client branch returns
    # bytes by patching the AsyncClient ctor to inject a MockTransport.
    expected_body = b"default-client-ok"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=expected_body)

    real_async_client = httpx.AsyncClient

    def _patched(*args: object, **kwargs: object) -> httpx.AsyncClient:
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_async_client(*args, **kwargs)  # type: ignore[arg-type]

    original = module_under_test.httpx.AsyncClient
    module_under_test.httpx.AsyncClient = _patched  # type: ignore[assignment]
    try:
        result = await fetch_url("https://example.invalid/page")
    finally:
        module_under_test.httpx.AsyncClient = original  # type: ignore[assignment]

    assert result == expected_body
