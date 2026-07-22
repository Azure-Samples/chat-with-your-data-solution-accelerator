"""Entry-point discovery for third-party provider extensions.

Loads `importlib.metadata.entry_points(group=...)` plugins at module
import time so third-party packages can self-register against the
shared `Registry[T]` primitive without editing core domain registries.

Caller pattern (used by every domain `registry.py` after first-party
side-effect imports):

    from backend.core.discovery import load_entry_points

    load_entry_points("cwyd.providers.databases")

Each loaded entry point is a module whose top-level `@registry.register(
"key")` decorator fires at `ep.load()` time. Failures are logged with
structured `extra` then re-raised so the lifespan halts (Hard Rule #14
loud-failure parity with first-party side-effect imports). `ep.load()`
is a function call, not an `import` statement, so Hard Rule #17 is
satisfied (same idiom as Pydantic `model_rebuild()`).
"""

import logging
from importlib.metadata import EntryPoint, entry_points

logger = logging.getLogger(__name__)


def load_entry_points(group: str) -> int:
    """Eager-load every entry point in `group`, returning load count.

    Each plugin module's `@registry.register(...)` decorators fire at
    `ep.load()` time. On failure, logs a structured warning then
    re-raises so lifespan startup halts (parity with first-party
    side-effect imports).
    """
    if not group:
        raise ValueError("load_entry_points: group must be a non-empty string")

    eps = entry_points(group=group)
    count = 0
    for ep in eps:
        _try_load_entry_point(ep, group)
        count += 1
    return count


def _try_load_entry_point(ep: EntryPoint, group: str) -> None:
    try:
        ep.load()
    except Exception:
        logger.exception(
            "Extension plugin failed to load",
            extra={
                "operation": "load_entry_point",
                "group": group,
                "plugin_name": ep.name,
                "plugin_value": ep.value,
            },
        )
        raise
    logger.info(
        "Extension plugin loaded",
        extra={
            "operation": "load_entry_point",
            "group": group,
            "plugin_name": ep.name,
            "plugin_value": ep.value,
        },
    )


__all__ = ["load_entry_points"]
