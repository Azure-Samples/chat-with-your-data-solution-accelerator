"""Azure Speech Service AAD token-mint helper.

Builds the Microsoft Entra ID authorization token the browser Speech
SDK (`microsoft-cognitiveservices-speech-sdk`) consumes -- without
ever touching a subscription key (Hard Rule #2 -- no Key Vault, no API
keys, UAMI / AAD only). The SDK takes the returned token plus the
region and talks to Azure Speech directly; no audio flows through this
backend.

Token flow (the documented Entra-ID pattern -- the SDK exchanges the
AAD token with the Speech service itself, so there is no server-side
STS / `issueToken` HTTP call):

1. Acquire an AAD bearer for the
   `https://cognitiveservices.azure.com/.default` scope using the
   per-app credential singleton (UAMI in production, AzureCli /
   DefaultAzureCredential locally) constructed by the
   `providers/credentials/` registry domain.
2. Return the SDK's authorization-token form
   `aad#<speech_account_resource_id>#<aad_token>`. The browser passes
   this verbatim to `SpeechConfig.fromAuthorizationToken(token, region)`;
   the SDK validates it against the account's custom-subdomain endpoint
   (Entra auth requires the custom domain -- regional endpoints do not
   support AAD).

Required RBAC: the workload identity must hold the
**Cognitive Services Speech User** role on the Speech account (role
def id `f2dc8367-1007-4938-bd23-fe263f013447`, already declared in
`infra/main.bicep`).
"""

import logging

from azure.core.credentials_async import AsyncTokenCredential
from azure.core.exceptions import AzureError

from backend.core.settings import SpeechSettings
from backend.core.types import AadScope

logger = logging.getLogger(__name__)


async def mint_speech_token(
    *,
    settings: SpeechSettings,
    credential: AsyncTokenCredential,
) -> str:
    """Build the Entra-ID Speech authorization token for the browser SDK.

    Returns the SDK's `aad#<resource_id>#<aad_token>` authorization-token
    form -- the value `SpeechConfig.fromAuthorizationToken(token, region)`
    expects for Microsoft Entra ID auth. No HTTP call is made; the SDK
    exchanges the AAD token with the Speech service itself.

    Raises:
        AzureError: AAD token acquisition failed (credential issue,
            tenant misconfiguration, missing RBAC at the token source,
            etc.).

    Per v2/docs/exception_handling_policy.md "Provider entry points":
    narrow catch, structured `logger.exception(extra={...})`, re-raise.
    The router layer translates this to a sanitized HTTPException for
    the browser.
    """
    log_extra = {
        "operation": "mint_speech_token",
        "provider": "speech",
        "region": settings.service_region,
        "speech_account": settings.service_name,
    }

    try:
        access_token = await credential.get_token(AadScope.COGNITIVE_SERVICES)
    except AzureError:
        logger.exception("speech token mint failed at AAD step", extra=log_extra)
        raise

    return f"aad#{settings.account_resource_id}#{access_token.token}"


__all__ = ["mint_speech_token"]
