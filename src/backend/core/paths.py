"""Shared path/extension helpers consumed by both the backend
ingestion service and the Functions ingestion blueprints, kept as a
``backend.core`` leaf so ``functions.*`` can import it one-way.
"""

from pathlib import PurePosixPath


def parser_key_for_path(name: str) -> str:
    """Lowercase extension (no dot) of a POSIX-style path / filename.

    ``PurePosixPath`` (not ``Path``) keeps separator handling stable
    across Windows dev hosts and Linux Functions runtimes -- the input
    is a blob path or URL path, both POSIX-style on every platform.
    """
    return PurePosixPath(name).suffix.lstrip(".").lower()
