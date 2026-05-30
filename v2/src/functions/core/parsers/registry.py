"""Parsers provider registry (ingestion-only plug-point).

Pillar: Stable Core
Phase: 6

Holds the `Registry[type[BaseParser]]` instance for ingestion-only parsers (PDF/DOCX/MD/TXT).
Concrete implementations (text_parser, pdf_parser, docx_parser, md_parser) self-register via `@registry.register("<ext>")`.
Eager side-effect imports of those concretes are added here as they land (Option SE-1 in dev_plan §2.4.5).

Caller pattern:

    from functions.core.parsers import registry as ingestion_parsers_registry
    parser = ingestion_parsers_registry.registry.get("txt")()
"""

from ._instance import registry as registry
from . import text_parser  # noqa: F401  # pyright: ignore[reportUnusedImport]
