"""Orchestrator provider registry.

Pillar: Stable Core
Phase: 3

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

from typing import Callable

from backend.core.registry import Registry

from .base import OrchestratorBase

# Generic is `Callable[..., OrchestratorBase]` rather than
# ``type[OrchestratorBase]`` because each concrete orchestrator
# constructor takes a *different* kwarg shape on top of
# ``settings`` + ``llm`` (e.g. ``langgraph`` takes ``search``,
# ``agent_framework`` takes ``agents_client`` + ``agent_id``; both
# absorb the rest via ``**_extras``). Widening to ``Callable[...]``
# admits that variance at the type level without leaking it into
# ``OrchestratorBase.__init__`` -- the router stays a single
# registry-keyed factory call (Hard Rule #4) and pyright stops
# flagging the per-provider kwargs as unknown parameters.
registry: Registry[Callable[..., OrchestratorBase]] = Registry("orchestrators")

# Side-effect imports (eager, one line per concrete orchestrator).
from . import agent_framework  # noqa: E402, F401
from . import langgraph  # noqa: E402, F401
