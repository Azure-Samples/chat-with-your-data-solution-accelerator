"""Agents-SDK provider registry (single plug-point).

Pillar: Stable Core
Phase: 4

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

from ._instance import registry as registry
from . import foundry  # noqa: F401
