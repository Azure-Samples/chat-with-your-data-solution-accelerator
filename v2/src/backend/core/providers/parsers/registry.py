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

from backend.core.registry import Registry

from .base import BaseParser

registry: Registry[type[BaseParser]] = Registry("parsers")
