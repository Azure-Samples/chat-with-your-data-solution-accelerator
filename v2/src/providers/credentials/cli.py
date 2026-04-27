"""Azure-CLI credentials provider.

Pillar: Stable Core
Phase: 2

Local-dev default when no UAMI is attached. Reuses the developer's
existing `az login` session so nothing has to be configured in `.env`
beyond the Bicep outputs. Never used in deployed environments.
"""
from __future__ import annotations

from azure.identity.aio import AzureCliCredential

from . import registry
from .base import BaseCredentialProvider


@registry.register("cli")
class CliCredentialProvider(BaseCredentialProvider):
    async def get_credential(self) -> AzureCliCredential:
        return AzureCliCredential()
