"""Credentials provider registry (single plug-point).

Pillar: Stable Core
Phase: 2

Holds the `Registry[type[BaseCredentialProvider]]` instance, the eager
side-effect imports of concrete providers, and the `select_default`
domain helper. Concrete providers (`cli`, `managed_identity`) call
`@registry.register("<key>")` against the registry instance below.

Caller pattern (Hard Rule #13):

    from backend.core.providers.credentials import registry as credentials_registry

    key = credentials_registry.select_default(settings.identity.uami_client_id)
    cred_provider = credentials_registry.registry.get(key)(settings=settings)
    async with await cred_provider.get_credential() as cred:
        ...
"""

# pyright: reportUnusedImport=false
# `from . import cli, managed_identity` below is an intentional
# side-effect import that triggers `@registry.register(...)`; pyright
# cannot see the side-effect and would flag it as unused (Hard Rule #4).

from backend.core.discovery import load_entry_points

from ._instance import registry as registry
from . import cli, managed_identity  # noqa: F401  (side-effect imports)

# Third-party plugins self-register via the `cwyd.providers.credentials`
# entry-point group per Hard Rule #11 registry-driven carve-out. See
# backend.core.discovery.load_entry_points for the loading contract.
load_entry_points("cwyd.providers.credentials")


def select_default(uami_client_id: str | None) -> str:
    """Heuristic for the default credentials provider key.

    A populated `AZURE_UAMI_CLIENT_ID` means the workload is running on
    Azure with a User-Assigned Managed Identity attached -- use it.
    Otherwise we are in local dev and the developer's `az login`
    session is the right credential source.
    """
    return "managed_identity" if uami_client_id else "cli"
