"""Admin router helpers.

Pillar: Stable Core
Phase: 5 (admin surface helpers)
"""

import logging
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from azure.core.exceptions import AzureError

from backend.core.agents.definitions import CWYD_AGENT
from backend.core.providers.agents.base import BaseAgentsProvider
from backend.core.providers.databases.base import BaseDatabaseClient
from backend.core.settings import AppSettings, IndexStore, OrchestratorName
from backend.core.tools.content_safety import rai_check
from backend.core.types import RuntimeConfig
from backend.models.admin import AdminConfig

__all__ = [
    "ConfigResolutionError",
    "host_only",
    "resolve_effective_config",
    "utcnow_iso",
    "validate_prompt_with_rai",
]

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


class ConfigResolutionError(Exception):
    """Effective configuration is invalid or self-contradictory.

    Pillar: Stable Core
    Phase: 8 (agent_framework default + Foundry IQ Knowledge Base retrieval)

    Raised by ``resolve_effective_config`` -- the single choke point
    where every admin override is overlaid on the env / code defaults
    -- when the resulting effective configuration cannot be served
    (for example, an orchestrator that requires an Azure AI Search
    index selected on a deployment that has none).

    Carries a human-readable ``message`` (surfaced to the operator in
    the response body), a ``reason`` discriminator, and a ``context``
    map of the conflicting ``field -> value`` pairs. The app-level
    handler maps it to HTTP 409 and emits one ERROR-level telemetry
    record built from these attributes; the resolver only raises (it
    does not log), so the record is written exactly once (ADR 0022).
    """

    def __init__(
        self,
        message: str,
        *,
        reason: str,
        context: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.reason = reason
        self.context: dict[str, str] = context or {}


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


# Reason discriminator carried by `ConfigResolutionError` when the
# effective orchestrator needs an Azure AI Search index the deployment
# does not have. Single value -> UPPER_SNAKE constant (per Hard Rule #11);
# promote to a `StrEnum` when a second reason joins it.
_REASON_ORCHESTRATOR_REQUIRES_AZURE_SEARCH = "orchestrator_requires_azure_search"


def resolve_effective_config(
    settings: AppSettings,
    overrides: RuntimeConfig | None,
) -> AdminConfig:
    """Resolve the effective admin config: env / code defaults overlaid
    with any persisted ``RuntimeConfig`` overrides.

    For each admin-mutable field the effective value is the override
    when the operator has set one (a non-``None`` value on
    ``overrides``) and the ``AppSettings`` env default -- or the
    built-in code constant for the prompt fields -- otherwise. A
    ``None`` on ``overrides`` means 'not overridden, fall through to
    the default': ``RuntimeConfig`` stores the mutable subset as
    ``T | None = None`` precisely so a boolean ``False`` override is
    distinguishable from 'unset', matching the RFC 7396 merge
    semantics of ``PATCH /api/admin/config``.

    Returns an ``AdminConfig`` -- the fully-resolved, non-optional
    view -- so request-time callers read concrete values
    (``effective.orchestrator_name``) without re-deriving the
    env-vs-override precedence. The audit fields (``updated_at`` /
    ``updated_by``) live on ``RuntimeConfig`` and are intentionally
    not part of the effective value surface.
    """
    values: dict[str, Any] = {
        "orchestrator_name": settings.orchestrator.name,
        "openai_temperature": settings.openai.temperature,
        "openai_max_tokens": settings.openai.max_tokens,
        "search_use_semantic_search": settings.search.use_semantic_search,
        "search_top_k": settings.search.top_k,
        "log_level": settings.observability.log_level,
        "content_safety_enabled": settings.content_safety.enabled,
        "cwyd_agent_instructions": CWYD_AGENT.instructions,
        "post_answering_prompt": "",
        "post_answering_enabled": False,
        "post_answering_filter_message": "",
    }
    if overrides is not None:
        for name in values:
            override_value = getattr(overrides, name)
            # `None` means 'not overridden, fall through to the default'
            # (RuntimeConfig stores the mutable subset as `T | None`);
            # only non-None values overlay the env / code default.
            if override_value is not None:
                values[name] = override_value

    # Cross-setting guard (ADR 0022): the agent_framework orchestrator
    # grounds on a Foundry IQ Knowledge Base whose only knowledge source
    # is the Azure AI Search index. A pgvector deployment has no such
    # index, so this effective pairing cannot be served. The check reads
    # the post-override orchestrator so an admin override into
    # agent_framework is rejected, not just the env default.
    effective_orchestrator = values["orchestrator_name"]
    if (
        settings.database.index_store == IndexStore.PGVECTOR
        and effective_orchestrator == OrchestratorName.AGENT_FRAMEWORK
    ):
        raise ConfigResolutionError(
            "Orchestrator 'agent_framework' grounds on a Foundry IQ "
            "Knowledge Base over an Azure AI Search index, but this "
            "deployment uses pgvector, which has no Knowledge Base "
            "source. Set CWYD_ORCHESTRATOR_NAME=langgraph for pgvector "
            "deployments.",
            reason=_REASON_ORCHESTRATOR_REQUIRES_AZURE_SEARCH,
            context={
                "index_store": str(settings.database.index_store),
                "configured_orchestrator": str(effective_orchestrator),
            },
        )

    return AdminConfig(**values)


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
