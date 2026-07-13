"""Parsers provider registry (ingestion-only plug-point).

Holds the `Registry[type[BaseParser]]` instance for ingestion-only parsers.
Concrete implementations self-register via `@registry.register(ParserKey.<EXT>)`:
`text_parser` (txt/md/json), `html_parser` (html), and
`document_intelligence_parser` (pdf/docx/jpeg/jpg/png). Together they cover
the full v1 supported-file-type set.
Eager side-effect imports of those concretes are registered here.

Caller pattern:

    from functions.core.parsers import registry as ingestion_parsers_registry
    parser = ingestion_parsers_registry.registry.get(ParserKey.TXT)()
"""

from ._instance import registry as registry  # noqa: F401
from . import text_parser  # noqa: F401  # pyright: ignore[reportUnusedImport]
from . import html_parser  # noqa: F401  # pyright: ignore[reportUnusedImport]
from . import document_intelligence_parser  # noqa: F401  # pyright: ignore[reportUnusedImport]
