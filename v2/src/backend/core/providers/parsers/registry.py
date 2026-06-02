"""Parsers provider registry (single plug-point).

Pillar: Stable Core
Phase: 6

Holds the `Registry[type[BaseParser]]` instance for the parsers
domain. Concrete ingestion-only parsers (PDF/DOCX/MD/HTML/TXT) live
under `v2/src/functions/core/parsers/` and self-register against this
registry via `@registry.register("<ext>")` (decision D1 in
development_plan §4.6.1). Eager side-effect imports of those
concretes are added here as they land (Option SE-1 in §2.4.5).

Caller pattern (Hard Rule #13):

    from backend.core.providers.parsers import registry as parsers_registry

    parser = parsers_registry.registry.get("txt")()
"""

from backend.core.discovery import load_entry_points
from backend.core.registry import Registry

from .base import BaseParser

registry: Registry[type[BaseParser]] = Registry("parsers")

# Third-party plugins self-register via the `cwyd.providers.parsers`
# entry-point group per Hard Rule #11 registry-driven carve-out. First-
# party concretes (PDF/DOCX/MD/HTML/TXT) live under
# `v2/src/functions/core/parsers/` and self-register from there at
# Functions startup; the backend itself ships no first-party parser
# imports against this registry. See backend.core.discovery
# .load_entry_points for the loading contract.
load_entry_points("cwyd.providers.parsers")
