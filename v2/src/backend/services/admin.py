"""Admin router helpers.

Pillar: Stable Core
Phase: 5 (admin surface helpers)
"""

import logging
from datetime import UTC, datetime
from urllib.parse import urlparse

from azure.core.exceptions import AzureError

from backend.core.providers.agents.base import BaseAgentsProvider
from backend.core.providers.databases.base import BaseDatabaseClient
from backend.core.tools.content_safety import rai_check

__all__ = ["host_only", "utcnow_iso", "validate_prompt_with_rai"]

logger = logging.getLogger(__name__)

# Operator-facing reason string returned when the RAI classifier
# rejects a submitted prompt. Single sentence so the FE can surface
# it inline next to the field without truncation; intentionally
# generic (no per-category enumeration) because `RAI_AGENT` is a
# binary TRUE/FALSE classifier that does not return a category.
RAI_PROMPT_REJECTION_REASON = (
    "The submitted prompt was rejected by the Responsible AI safety "
    "classifier and was not persisted."
)


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


async def validate_prompt_with_rai(
    text: str,
    agents: BaseAgentsProvider,
    db: BaseDatabaseClient,
) -> str | None:
    """Classify ``text`` through `RAI_AGENT`; return rejection reason
    or ``None`` when accepted.

    Returns ``None`` for accepted prompts (TRUE classification or
    empty / whitespace-only input). Returns a single-sentence
    operator-facing reason string when the classifier returns FALSE,
    fails the run, or produces no parseable verdict (fail-closed --
    mirrors `rai_check`'s contract). The reason string is a constant
    so callers can rely on its shape for UI surfacing.

    The underlying `rai_check` already short-circuits empty / whitespace
    input without a Foundry round-trip; the explicit guard here is
    documentation, not redundancy -- callers that pass an empty
    prompt expect a no-op return without paying Foundry latency.
    """
    if not text or not text.strip():
        return None

    try:
        accepted = await rai_check(text, agents, db)
    except AzureError:
        logger.exception(
            "RAI prompt validation failed against Foundry SDK.",
            extra={
                "operation": "validate_prompt_with_rai",
                "provider": "agents",
            },
        )
        raise

    return None if accepted else RAI_PROMPT_REJECTION_REASON
