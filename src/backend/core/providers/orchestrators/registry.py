"""Orchestrator provider registry.

Holds the ``Registry[type[OrchestratorBase]]`` instance plus the eager
side-effect imports of every concrete orchestrator. Imports fire each
concrete's ``@registry.register("<key>")`` decorator at module-load
time so the registry is fully populated as soon as any caller does
``from backend.core.providers.orchestrators import registry as
orchestrators_registry``.

Hard Rule #4 key invariant: registered keys (``"langgraph"``,
``"agent_framework"``) MUST equal the ``settings.orchestrator.name``
Literal values so dispatch is registry-only -- no ``if/elif`` over
orchestrator names anywhere downstream (see
``routers/conversation.py`` + the AST-counted gate
``test_router_uses_registry_dispatch_no_hardcoded_provider_names``).
"""

# pyright: reportUnusedImport=false
# `from . import <module>` lines below are intentional side-effect
# imports that trigger `@registry.register(...)`; pyright cannot see
# the side-effect and would flag them as unused (Hard Rule #4).

from backend.core.discovery import load_entry_points

from ._instance import registry as registry  # noqa: F401
from . import agent_framework  # noqa: F401
from . import langgraph  # noqa: F401

# Third-party plugins self-register via the `cwyd.providers.orchestrators`
# entry-point group per Hard Rule #11 registry-driven carve-out. See
# backend.core.discovery.load_entry_points for the loading contract.
load_entry_points("cwyd.providers.orchestrators")
