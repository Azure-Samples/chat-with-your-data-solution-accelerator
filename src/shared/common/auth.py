"""Authentication utilities for Azure App Service EasyAuth headers.

When deployed behind Azure App Service authentication, the platform injects
``X-Ms-Client-Principal-*`` headers.  In local development these headers are
absent and a dev-mode fallback is used.
"""

from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass

from fastapi import Request

logger = logging.getLogger(__name__)

_DEV_PRINCIPAL_ID = "00000000-0000-0000-0000-000000000000"
_DEV_USER_NAME = "dev_user@localhost"


@dataclass(frozen=True)
class AuthenticatedUser:
    user_principal_id: str
    user_name: str
    auth_provider: str
    client_principal_b64: str
    aad_id_token: str
    tenant_id: str


def get_authenticated_user(request: Request) -> AuthenticatedUser:
    """Extract user identity from EasyAuth headers, or return dev fallback."""
    principal_id = request.headers.get("X-Ms-Client-Principal-Id")

    if not principal_id:
        # Local development — no EasyAuth headers present
        return AuthenticatedUser(
            user_principal_id=_DEV_PRINCIPAL_ID,
            user_name=_DEV_USER_NAME,
            auth_provider="dev",
            client_principal_b64="",
            aad_id_token="",
            tenant_id="",
        )

    b64 = request.headers.get("X-Ms-Client-Principal", "")
    return AuthenticatedUser(
        user_principal_id=principal_id,
        user_name=request.headers.get("X-Ms-Client-Principal-Name", ""),
        auth_provider=request.headers.get("X-Ms-Client-Principal-Idp", ""),
        client_principal_b64=b64,
        aad_id_token=request.headers.get("X-Ms-Token-Aad-Id-Token", ""),
        tenant_id=_extract_tenant_id(b64),
    )


def _extract_tenant_id(client_principal_b64: str) -> str:
    """Decode the base64-encoded client principal to extract tenant_id."""
    if not client_principal_b64:
        return ""
    try:
        decoded = base64.b64decode(client_principal_b64)
        user_info = json.loads(decoded)
        return user_info.get("tid", "")
    except Exception:
        logger.exception("Failed to decode client principal")
        return ""
