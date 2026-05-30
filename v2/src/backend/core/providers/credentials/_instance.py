"""Registry instance for the credentials provider domain.

Pillar: Stable Core
Phase: 2

Holds the `Registry[type[BaseCredentialProvider]]` instance in a leaf
module so `registry.py` can be top-imports-only per Hard Rule #17. The
public surface (eager concrete imports + `select_default` helper) stays
in `registry.py`.
"""

from backend.core.registry import Registry

from .base import BaseCredentialProvider

registry: Registry[type[BaseCredentialProvider]] = Registry("credentials")
