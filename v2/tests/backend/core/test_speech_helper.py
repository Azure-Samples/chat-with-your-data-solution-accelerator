"""Tests for `backend.core.speech` (S1 / SPEECH-MVP, Phase 4 polish).

Pillar: Stable Core
Phase: 4
"""

import logging
from typing import Any

import httpx
import pytest
from azure.core.credentials import AccessToken
from azure.core.exceptions import ClientAuthenticationError

from backend.core.settings import SpeechSettings
from backend.core.speech import mint_speech_token


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_REGION = "eastus2"
_TOKEN = "ey-fake-aad-token"
_SPEECH_TOKEN = "fake-speech-auth-token-body"
_SERVICE_NAME = "spch-cwyd001"
_RESOURCE_ID = (
    "/subscriptions/x/resourceGroups/y/providers/"
    "Microsoft.CognitiveServices/accounts/spch-cwyd001"
)


class _StubCredential:
    """Minimal AsyncTokenCredential stub.

    `mint_speech_token` only awaits `get_token(scope)` and reads
    `.token` off the result, so the surface area is tiny.
    """

    def __init__(
        self,
        *,
        token: str = _TOKEN,
        raise_on_get: BaseException | None = None,
    ) -> None:
        self._token = token
        self._raise = raise_on_get
        self.calls: list[tuple[Any, ...]] = []

    async def get_token(self, *scopes: str, **_: Any) -> AccessToken:
        self.calls.append(scopes)
        if self._raise is not None:
            raise self._raise
        return AccessToken(self._token, expires_on=9999999999)

    async def close(self) -> None:  # pragma: no cover - not exercised
        return None


def _settings() -> SpeechSettings:
    return SpeechSettings(
        service_name=_SERVICE_NAME,
        service_region=_REGION,
        account_resource_id=_RESOURCE_ID,
    )


def _mock_client(handler: httpx.MockTransport) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=handler, timeout=5.0)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mints_token_via_aad_and_returns_response_body() -> None:
    captured: dict[str, Any] = {}

    def _handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["method"] = request.method
        captured["headers"] = dict(request.headers)
        captured["body"] = request.content
        return httpx.Response(200, text=_SPEECH_TOKEN)

    cred = _StubCredential()
    async with _mock_client(httpx.MockTransport(_handler)) as client:
        token = await mint_speech_token(
            settings=_settings(),
            credential=cred,
            http_client=client,
        )

    assert token == _SPEECH_TOKEN
    # AAD scope is the cognitive-services resource scope -- never the
    # ARM scope or a per-region scope.
    assert cred.calls == [("https://cognitiveservices.azure.com/.default",)]
    # Custom-subdomain issueToken endpoint -- AAD (Entra ID) auth requires
    # the account's custom domain; the regional host does not support it
    # (BUG-0070 root cause 2; matches v1's `speechService.outputs.endpoint`).
    # POST, empty body, AAD bearer + resource-id headers.
    assert captured["method"] == "POST"
    assert captured["url"] == (
        f"https://{_SERVICE_NAME}.cognitiveservices.azure.com/sts/v1.0/issueToken"
    )
    assert captured["headers"]["authorization"] == f"Bearer {_TOKEN}"
    assert captured["headers"]["x-ms-cognitiveservices-resource-id"] == _RESOURCE_ID
    assert captured["body"] == b""


# ---------------------------------------------------------------------------
# Failure paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_aad_failure_is_logged_and_reraised(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """AAD acquisition failure must surface as the original `AzureError`
    subclass and be logged at exception level so operators see the
    failing scope / region in App Insights.
    """
    cred = _StubCredential(
        raise_on_get=ClientAuthenticationError("no managed identity bound")
    )
    # Empty handler: must never be called when AAD step fails.
    transport_calls: list[httpx.Request] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        transport_calls.append(request)
        return httpx.Response(500)

    with caplog.at_level(logging.ERROR, logger="backend.core.speech"):
        async with _mock_client(httpx.MockTransport(_handler)) as client:
            with pytest.raises(ClientAuthenticationError):
                await mint_speech_token(
                    settings=_settings(),
                    credential=cred,
                    http_client=client,
                )

    assert transport_calls == []
    assert any(
        "speech token mint failed at AAD step" in record.message
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_http_failure_is_logged_and_reraised(
    caplog: pytest.LogCaptureFixture,
) -> None:
    def _handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="forbidden")

    with caplog.at_level(logging.ERROR, logger="backend.core.speech"):
        async with _mock_client(httpx.MockTransport(_handler)) as client:
            with pytest.raises(httpx.HTTPStatusError):
                await mint_speech_token(
                    settings=_settings(),
                    credential=_StubCredential(),
                    http_client=client,
                )

    assert any(
        "speech token mint failed at issueToken endpoint" in record.message
        for record in caplog.records
    )


# ---------------------------------------------------------------------------
# Lifecycle: helper-owned client is closed; caller-owned client is not.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_caller_owned_client_is_not_closed_by_helper() -> None:
    def _handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=_SPEECH_TOKEN)

    async with _mock_client(httpx.MockTransport(_handler)) as client:
        await mint_speech_token(
            settings=_settings(),
            credential=_StubCredential(),
            http_client=client,
        )
        # Helper must NOT close a client it didn't create.
        assert not client.is_closed


@pytest.mark.asyncio
async def test_helper_owned_client_path_executes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When `http_client` is None the helper constructs + closes its own
    `httpx.AsyncClient`. Patch the constructor to hand back a
    MockTransport-backed client and confirm `aclose` is awaited.
    """
    closed: list[bool] = []

    def _handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=_SPEECH_TOKEN)

    real_client = httpx.AsyncClient(transport=httpx.MockTransport(_handler))
    real_aclose = real_client.aclose

    async def _tracking_aclose() -> None:
        closed.append(True)
        await real_aclose()

    real_client.aclose = _tracking_aclose  # type: ignore[method-assign]

    def _factory(*_args: Any, **_kwargs: Any) -> httpx.AsyncClient:
        return real_client

    monkeypatch.setattr("backend.core.speech.httpx.AsyncClient", _factory)

    token = await mint_speech_token(
        settings=_settings(),
        credential=_StubCredential(),
        http_client=None,
    )

    assert token == _SPEECH_TOKEN
    assert closed == [True]
