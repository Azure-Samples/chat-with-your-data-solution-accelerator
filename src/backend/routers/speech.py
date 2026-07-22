"""Speech-to-text router (mints AAD-bearer Speech tokens for the browser).

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

from azure.core.exceptions import AzureError
from fastapi import APIRouter, HTTPException, status

from backend.core.speech import mint_speech_token
from backend.dependencies import CredentialProviderDep, SettingsDep
from backend.models.errors import ErrorResponse
from backend.models.speech import SpeechConfig

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/speech", tags=["speech"])


@router.get(
    "",
    response_model=SpeechConfig,
    summary="Get speech config + token",
    description=(
        "Return the Speech SDK configuration (region, language, voice) "
        "along with a freshly minted, short-lived AAD bearer token for "
        "browser-side speech-to-text. Responds 503 when the Speech service "
        "is not configured and 502 when token minting fails."
    ),
    responses={
        502: {
            "model": ErrorResponse,
            "description": "Speech token mint failed.",
        },
        503: {
            "model": ErrorResponse,
            "description": "Speech service not configured.",
        },
    },
)
async def get_speech_config(
    settings: SettingsDep,
    credential_provider: CredentialProviderDep,
) -> SpeechConfig:
    """Return Speech SDK config + a freshly minted AAD-bearer token.

    503 ``Speech service not configured`` when ``service_region`` is
    empty -- mirrors the ``Database not configured`` shape used by
    the history router so the FE can render a consistent
    "feature-unavailable" banner.

    502 ``Speech token mint failed`` when the AAD token acquisition
    fails. The underlying exception is logged with structured context
    inside :func:`mint_speech_token`; the router scrubs the detail so
    SDK error messages never leak to the browser.
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
    except AzureError as exc:
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
        languages=[
            lang.strip()
            for lang in settings.speech.recognizer_languages.split(",")
            if lang.strip()
        ],
    )


__all__ = ["router"]
