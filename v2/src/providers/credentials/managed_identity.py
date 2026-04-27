"""Managed-identity credentials provider.

Pillar: Stable Core
Phase: 2

Production default. Returns `azure.identity.aio.DefaultAzureCredential`,
which on Azure transparently picks up the User-Assigned Managed Identity
attached to the host (Container App / Function App / App Service) -- no
client secret, no Key Vault. When `AZURE_UAMI_CLIENT_ID` is set we pin
DefaultAzureCredential to that specific UAMI so multi-identity hosts
do not silently fall back to a system-assigned identity.
"""
from __future__ import annotations

from azure.identity.aio import DefaultAzureCredential

from . import registry
from .base import BaseCredentialProvider


@registry.register("managed_identity")
class ManagedIdentityCredentialProvider(BaseCredentialProvider):
    async def get_credential(self) -> DefaultAzureCredential:
        client_id = self._settings.identity.uami_client_id or None
        return DefaultAzureCredential(managed_identity_client_id=client_id)
