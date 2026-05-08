"""Azure Speech Service AAD token-mint helper.

Pillar: Stable Core
Phase: 4 (S1 / SPEECH-MVP -- pulled forward from Phase 5 task #38)

Mints a short-lived (10-minute) Azure Speech Service authorization
token without ever touching a subscription key. The browser SDK
(`microsoft-cognitiveservices-speech-sdk`) takes the returned token
plus the region and talks to Azure Speech directly -- no audio ever
flows through this backend.

Token-mint flow (replaces v1's `Ocp-Apim-Subscription-Key` shortcut,
banned by Hard Rule #2 -- no Key Vault, no API keys, UAMI/AAD only):

1. Acquire an AAD bearer for the
   `https://cognitiveservices.azure.com/.default` scope using the
   per-app credential singleton (UAMI in production, AzureCli /
   DefaultAzureCredential locally) constructed by the
   `providers/credentials/` registry domain.
2. POST to `https://{region}.api.cognitive.microsoft.com/sts/v1.0/issueToken`
   with `Authorization: Bearer <aad_token>` and
   `x-ms-cognitiveservices-resource-id: <speech_account_resource_id>`.
   Empty body, plain-text response.
3. Return the response body verbatim -- the Speech SDK consumes it as
   an opaque authorization token.

Required RBAC: the workload identity must hold the
**Cognitive Services Speech User** role on the Speech account (role
def id `f2dc8367-1007-4938-bd23-fe263f013447`, already declared in
`v2/infra/main.bicep`).
"""

import logging

import httpx
from azure.core.credentials_async import AsyncTokenCredential
from azure.core.exceptions import AzureError

from backend.core.settings import SpeechSettings

logger = logging.getLogger(__name__)


_SPEECH_AAD_SCOPE = "https://cognitiveservices.azure.com/.default"
_TOKEN_MINT_TIMEOUT_SECONDS = 10.0


def _token_mint_url(region: str) -> str:
    return f"https://{region}.api.cognitive.microsoft.com/sts/v1.0/issueToken"


async def mint_speech_token(
    *,
    settings: SpeechSettings,
    credential: AsyncTokenCredential,
    http_client: httpx.AsyncClient | None = None,
) -> str:
    """Mint a 10-minute Azure Speech authorization token via AAD.

    Returns the token as plain text (the format the Speech SDK's
    `SpeechConfig.fromAuthorizationToken(token, region)` expects).

    Raises:
        AzureError: AAD token acquisition failed (credential issue,
            tenant misconfiguration, etc.).
        httpx.HTTPError: The Speech `issueToken` endpoint returned a
            non-2xx response or the request itself failed (network,
            timeout, DNS).

    Per v2/docs/exception_handling_policy.md "Provider entry points":
    narrow catches, structured `logger.exception(extra={...})`, re-raise.
    The router layer translates these to a sanitized HTTPException for
    the browser.
    """
    region = settings.service_region
    log_extra = {
        "operation": "mint_speech_token",
        "provider": "speech",
        "region": region,
        "speech_account": settings.service_name,
    }

    try:
        access_token = await credential.get_token(_SPEECH_AAD_SCOPE)
    except AzureError:
        logger.exception("speech token mint failed at AAD step", extra=log_extra)
        raise

    headers = {
        "Authorization": f"Bearer {access_token.token}",
        "x-ms-cognitiveservices-resource-id": settings.account_resource_id,
        "Content-Length": "0",
    }
    url = _token_mint_url(region)

    owns_client = http_client is None
    client = http_client or httpx.AsyncClient(timeout=_TOKEN_MINT_TIMEOUT_SECONDS)
    try:
        try:
            response = await client.post(url, headers=headers)
            response.raise_for_status()
        except httpx.HTTPError:
            logger.exception(
                "speech token mint failed at issueToken endpoint",
                extra=log_extra,
            )
            raise
    finally:
        if owns_client:
            await client.aclose()

    return response.text


__all__ = ["mint_speech_token"]
