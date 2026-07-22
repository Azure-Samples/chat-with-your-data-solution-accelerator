"""Registry instance for the agents-SDK provider domain.

Holds the `Registry[type[BaseAgentsProvider]]` instance in a leaf
module so `registry.py` can be top-imports-only per Hard Rule #17. The
public surface (eager concrete import of `foundry`) stays in
`registry.py`.
"""

from backend.core.registry import Registry

from .base import BaseAgentsProvider

registry: Registry[type[BaseAgentsProvider]] = Registry("agents")
