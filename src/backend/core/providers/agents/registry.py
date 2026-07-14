"""Agents-SDK provider registry (single plug-point).

Holds the `Registry[type[BaseAgentsProvider]]` instance and the eager
side-effect import of `foundry` (which calls
`@registry.register("foundry")` at import time).

Caller pattern (Hard Rule #13):

    from backend.core.providers.agents import registry as agents_registry

    provider = agents_registry.registry.get("foundry")(
        settings=settings, credential=credential
    )
    client = provider.get_client()  # azure.ai.agents.aio.AgentsClient
"""

# pyright: reportUnusedImport=false
# `from . import foundry` below is an intentional side-effect import
# that triggers `@registry.register("foundry")`; pyright cannot see
# the side-effect and would flag it as unused (Hard Rule #4).

from backend.core.discovery import load_entry_points

from ._instance import registry as registry  # noqa: F401
from . import foundry  # noqa: F401

# Third-party plugins self-register via the `cwyd.providers.agents`
# entry-point group per Hard Rule #11 registry-driven carve-out. See
# backend.core.discovery.load_entry_points for the loading contract.
load_entry_points("cwyd.providers.agents")
