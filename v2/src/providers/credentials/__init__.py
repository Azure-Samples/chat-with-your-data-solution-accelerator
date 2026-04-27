"""Credentials provider domain (registry-keyed).

Pillar: Stable Core
Phase: 2

Single plug-point for acquiring an `AsyncTokenCredential`. Backend,
functions, and pipelines all call `credentials.create(...)` -- never
`DefaultAzureCredential()` directly. This keeps test fakes and local-
dev shims (e.g. AzureCliCredential) drop-in swappable.

Recipe (per §3.5 of v2/docs/development_plan.md):

    cred_provider = credentials.create("managed_identity", settings=settings)
    async with await cred_provider.get_credential() as cred:
        ...
"""
from __future__ import annotations

from shared.registry import Registry

from .base import BaseCredentialProvider

registry: Registry[type[BaseCredentialProvider]] = Registry("credentials")

# Eager imports trigger @registry.register(...) on each provider module.
# Caller code never imports a provider class directly -- it goes through
# `create(key, ...)` so swapping providers is a one-config change.
from . import cli, managed_identity  # noqa: E402, F401  (side-effect imports)


def create(key: str, **kwargs: object) -> BaseCredentialProvider:
    """Instantiate the provider registered under `key`.

    `key` is case-insensitive (handled by `Registry`).
    """
    return registry.get(key)(**kwargs)


def select_default(uami_client_id: str | None) -> str:
    """Heuristic for the default credentials provider key.

    A populated `AZURE_UAMI_CLIENT_ID` means the workload is running on
    Azure with a User-Assigned Managed Identity attached -- use it.
    Otherwise we are in local dev and the developer's `az login`
    session is the right credential source.
    """
    return "managed_identity" if uami_client_id else "cli"


__all__ = ["BaseCredentialProvider", "create", "registry", "select_default"]
