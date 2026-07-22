"""Parsers provider registry (single plug-point).

Holds the `Registry[type[BaseParser]]` instance for the parsers
domain. Concrete ingestion-only parsers (PDF/DOCX/MD/HTML/TXT) live
under `src/functions/core/parsers/` and self-register against this
registry via `@registry.register("<ext>")`. Eager side-effect imports
of those concretes are added here.

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
# `src/functions/core/parsers/` and self-register from there at
# Functions startup; the backend itself ships no first-party parser
# imports against this registry. See backend.core.discovery
# .load_entry_points for the loading contract.
load_entry_points("cwyd.providers.parsers")
