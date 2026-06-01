"""Admin router helpers.

Pillar: Stable Core
Phase: 5 (admin surface helpers)
"""

from datetime import UTC, datetime
from urllib.parse import urlparse

__all__ = ["host_only", "utcnow_iso"]


def host_only(url: str) -> str:
    """Return the host portion of ``url`` or empty string when unset.

    Keeps the project endpoint discoverable for operators (which
    Foundry account am I pointed at?) without leaking the full URL
    path / query, which can carry tenant or project identifiers in
    some Foundry deployment shapes.
    """
    if not url:
        return ""
    return urlparse(url).netloc


def utcnow_iso() -> str:
    """ISO-8601 UTC timestamp with timezone suffix. Matches the
    ``_utcnow_iso`` shape in ``backend/core/providers/databases/cosmosdb.py``
    so persisted ``RuntimeConfig`` rows are comparable across providers.
    """
    return datetime.now(UTC).isoformat()
