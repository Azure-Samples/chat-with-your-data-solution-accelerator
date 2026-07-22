"""Tests for `backend.core.speech`."""

import logging
from typing import Any

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


# ---------------------------------------------------------------------------
# Token format: the documented Entra-ID `aad#{resourceId}#{aadToken}` form
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_returns_aad_format_authorization_token() -> None:
    """The helper returns the SDK's `aad#{resourceId}#{aadToken}` form --
    the documented Microsoft Entra ID pattern the browser SDK consumes via
    `SpeechConfig.fromAuthorizationToken(token, region)`. No HTTP call is
    made: the SDK exchanges the AAD token with the Speech service itself.
    """
    cred = _StubCredential()

    token = await mint_speech_token(settings=_settings(), credential=cred)

    assert token == f"aad#{_RESOURCE_ID}#{_TOKEN}"
    # AAD scope is the cognitive-services resource scope -- never the ARM
    # scope or a per-region scope.
    assert cred.calls == [("https://cognitiveservices.azure.com/.default",)]


# ---------------------------------------------------------------------------
# Failure path: AAD acquisition
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_aad_failure_is_logged_and_reraised(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """AAD acquisition failure must surface as the original `AzureError`
    subclass and be logged at exception level so operators see the
    failing scope / account in App Insights.
    """
    cred = _StubCredential(
        raise_on_get=ClientAuthenticationError("no managed identity bound")
    )

    with caplog.at_level(logging.ERROR, logger="backend.core.speech"):
        with pytest.raises(ClientAuthenticationError):
            await mint_speech_token(settings=_settings(), credential=cred)

    assert any(
        "speech token mint failed at AAD step" in record.message
        for record in caplog.records
    )
