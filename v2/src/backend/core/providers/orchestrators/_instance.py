"""Registry instance for the orchestrators provider domain.

Pillar: Stable Core
Phase: 3

Holds the `Registry[Callable[..., OrchestratorBase]]` instance in a
leaf module so `registry.py` can be top-imports-only per Hard Rule
#17. The public surface (eager concrete imports of `langgraph` +
`agent_framework`) stays in `registry.py`.
"""

from typing import Callable

from backend.core.registry import Registry

from .base import OrchestratorBase

# Generic is `Callable[..., OrchestratorBase]` rather than
# `type[OrchestratorBase]` because each concrete orchestrator
# constructor takes a *different* kwarg shape on top of
# `settings` + `llm` (e.g. `langgraph` takes `search`,
# `agent_framework` takes `agents_client` + `agent_id`; both
# absorb the rest via `**_extras`). Widening to `Callable[...]`
# admits that variance at the type level without leaking it into
# `OrchestratorBase.__init__` -- the router stays a single
# registry-keyed factory call (Hard Rule #4) and pyright stops
# flagging the per-provider kwargs as unknown parameters.
registry: Registry[Callable[..., OrchestratorBase]] = Registry("orchestrators")
