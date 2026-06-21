"""Tests for ``/api/speech`` router (S1 / SPEECH-MVP, Phase 4 polish).

Pillar: Stable Core
Phase: 4

Self-contained: builds a minimal FastAPI app from just the speech
router so the test does not depend on B4's full app wiring.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from azure.core.credentials import AccessToken
from azure.core.exceptions import ClientAuthenticationError
from fastapi import FastAPI

from backend.core.settings import SpeechSettings
from backend.dependencies import get_app_settings, get_credential_provider
from backend.routers import speech as speech_router


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _StubCredential:
    async def get_token(self, *_scopes: str, **_: Any) -> AccessToken:
        return AccessToken("aad-bearer", expires_on=9999999999)

    async def close(self) -> None:  # pragma: no cover
        return None


class _StubCredentialProvider:
    def __init__(self, credential: Any | None = None) -> None:
        self._credential = credential or _StubCredential()

    async def get_credential(self) -> Any:
        return self._credential


def _settings_with_speech(*, region: str = "eastus2") -> Any:
    """Build a stand-in `AppSettings` with only `.speech` populated.

    Following the history-router test pattern: full `AppSettings`
    construction would force every other AZURE_* env var to be set
    (DatabaseSettings.model_validator demands it). MagicMock keeps
    the test focused on the speech surface.
    """
    speech = SpeechSettings(
        service_name="spch-cwyd001",
        service_region=region,
        account_resource_id=(
            "/subscriptions/x/resourceGroups/y/providers/"
            "Microsoft.CognitiveServices/accounts/spch-cwyd001"
        ),
    )
    settings = MagicMock()
    settings.speech = speech
    return settings


def _build_app(settings: Any, credential_provider: Any) -> FastAPI:
    app = FastAPI()
    app.include_router(speech_router.router)
    app.dependency_overrides[get_app_settings] = lambda: settings
    app.dependency_overrides[get_credential_provider] = lambda: credential_provider
    return app


def _client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


async def test_get_speech_returns_token_region_languages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """200 with the SDK-bootstrap shape; languages parsed from the
    comma-separated env value.
    """
    fake_mint = AsyncMock(return_value="speech-token-xyz")
    monkeypatch.setattr(
        "backend.routers.speech.mint_speech_token", fake_mint
    )

    app = _build_app(_settings_with_speech(), _StubCredentialProvider())
    async with _client(app) as client:
        resp = await client.get("/api/speech")

    assert resp.status_code == 200
    body = resp.json()
    assert body == {
        "token": "speech-token-xyz",
        "region": "eastus2",
        # v1 parity default split into a real list.
        "languages": ["en-US", "fr-FR", "de-DE", "it-IT"],
    }

    # Confirm the helper got the right inputs.
    assert fake_mint.await_count == 1
    kwargs = fake_mint.await_args.kwargs
    assert kwargs["settings"].service_region == "eastus2"
    assert kwargs["settings"].account_resource_id.endswith("/spch-cwyd001")


async def test_languages_split_strips_whitespace_and_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "backend.routers.speech.mint_speech_token",
        AsyncMock(return_value="t"),
    )
    settings = _settings_with_speech()
    settings.speech = SpeechSettings(
        service_name="spch-cwyd001",
        service_region="eastus2",
        account_resource_id="/x",
        recognizer_languages=" en-US , , es-ES ",
    )
    app = _build_app(settings, _StubCredentialProvider())
    async with _client(app) as client:
        resp = await client.get("/api/speech")

    assert resp.status_code == 200
    assert resp.json()["languages"] == ["en-US", "es-ES"]


# ---------------------------------------------------------------------------
# 503 when speech is not configured
# ---------------------------------------------------------------------------


async def test_returns_503_when_speech_region_unset() -> None:
    app = _build_app(
        _settings_with_speech(region=""),
        _StubCredentialProvider(),
    )
    async with _client(app) as client:
        resp = await client.get("/api/speech")

    assert resp.status_code == 503
    assert resp.json() == {"detail": "Speech service not configured."}


# ---------------------------------------------------------------------------
# 502 when token mint fails (AAD acquisition)
# ---------------------------------------------------------------------------


async def test_returns_502_when_aad_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "backend.routers.speech.mint_speech_token",
        AsyncMock(
            side_effect=ClientAuthenticationError("UAMI not bound to workload")
        ),
    )
    app = _build_app(_settings_with_speech(), _StubCredentialProvider())
    async with _client(app) as client:
        resp = await client.get("/api/speech")

    assert resp.status_code == 502
    # SDK error message must NOT leak; only the sanitized detail.
    assert resp.json() == {"detail": "Speech token mint failed."}


# ---------------------------------------------------------------------------
# OpenAPI shape (FE consumes the generated client)
# ---------------------------------------------------------------------------


def test_openapi_exposes_speech_config_schema() -> None:
    """The generated TS client (F1 OpenAPI regen) reads the schema from
    the spec; if `SpeechConfig` ever loses a field the FE wrapper will
    silently lose typing. Pin the contract here.
    """
    app = _build_app(_settings_with_speech(), _StubCredentialProvider())
    spec = app.openapi()
    schema = spec["components"]["schemas"]["SpeechConfig"]
    props = schema["properties"]
    assert set(props.keys()) == {"token", "region", "languages"}
    assert props["languages"]["type"] == "array"
    assert props["languages"]["items"]["type"] == "string"
    # Route exists at the documented path with a 200 response.
    op = spec["paths"]["/api/speech"]["get"]
    assert "200" in op["responses"]
