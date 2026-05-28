"""Speech-to-text router (mints AAD-bearer Speech tokens for the browser).

Pillar: Stable Core
Phase: 4 (S1 / SPEECH-MVP)

Single endpoint: ``GET /api/speech`` returns
``{token, region, languages}`` for the
``microsoft-cognitiveservices-speech-sdk`` running in the browser.
The backend never streams audio; it only mints the short-lived
(10-min) authorization token via AAD (no subscription key, Hard
Rule #2).

Behaves like the v1 ``/api/speech`` route (for FE parity) but swaps
the v1 ``Ocp-Apim-Subscription-Key`` shortcut for the AAD-bearer
flow implemented in :mod:`backend.core.speech`.
"""

import logging

import httpx
from azure.core.exceptions import AzureError
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from backend.core.speech import mint_speech_token
from backend.dependencies import CredentialProviderDep, SettingsDep

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/speech", tags=["speech"])


class SpeechConfig(BaseModel):
    """Browser-consumable Speech-SDK bootstrap payload."""

    token: str = Field(description="10-minute Azure Speech authorization token.")
    region: str = Field(description="Azure region of the Speech account.")
    languages: list[str] = Field(
        description=(
            "BCP-47 language tags the recognizer should auto-detect. "
            "Defaults to v1's `en-US,fr-FR,de-DE,it-IT`."
        )
    )


def _split_languages(raw: str) -> list[str]:
    return [lang.strip() for lang in raw.split(",") if lang.strip()]


@router.get("", response_model=SpeechConfig)
async def get_speech_config(
    settings: SettingsDep,
    credential_provider: CredentialProviderDep,
) -> SpeechConfig:
    """Return Speech SDK config + a freshly minted AAD-bearer token.

    503 ``Speech service not configured`` when ``service_region`` is
    empty -- mirrors the ``Database not configured`` shape used by
    the history router so the FE can render a consistent
    "feature-unavailable" banner.

    502 ``Speech token mint failed`` when the AAD or issueToken HTTP
    call fails. The underlying exception is logged with structured
    context inside :func:`mint_speech_token`; the router scrubs the
    detail so SDK error messages never leak to the browser.
    """
    if not settings.speech.service_region:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Speech service not configured.",
        )

    credential = await credential_provider.get_credential()
    try:
        token = await mint_speech_token(
            settings=settings.speech,
            credential=credential,
        )
    except (AzureError, httpx.HTTPError) as exc:
        # Helper already logged with `extra={...}` -- here we only
        # translate to a sanitized HTTP error for the FE.
        logger.warning(
            "speech token mint surfaced as 502: %s",
            exc.__class__.__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Speech token mint failed.",
        ) from exc

    return SpeechConfig(
        token=token,
        region=settings.speech.service_region,
        languages=_split_languages(settings.speech.recognizer_languages),
    )


__all__ = ["router", "SpeechConfig"]
