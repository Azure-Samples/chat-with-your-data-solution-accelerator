"""Admin router helpers."""

import logging
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from azure.core.exceptions import AzureError

from backend.core.agents.definitions import (
    CWYD_AGENT,
    PROMPT_REVIEW_AGENT,
    resolve_cwyd_instructions,
)
from backend.core.agents.presets import (
    DEFAULT_ASSISTANT_TYPE,
    DEFAULT_POST_ANSWERING_FILTER_MESSAGE,
    DEFAULT_POST_ANSWERING_PROMPT,
    AssistantType,
    body_for,
)
from backend.core.providers.agents.base import BaseAgentsProvider
from backend.core.providers.databases.base import BaseDatabaseClient
from backend.core.settings import AppSettings
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


def _normalize_prompt(text: str) -> str:
    """Normalize a prompt for deterministic allow-list comparison.

    Unifies line endings and strips surrounding whitespace so a
    verbatim re-submission of a built-in body matches regardless of
    CR/LF or trailing-newline drift -- the admin editor seeds the raw
    body (`GET /api/admin/config` returns `CWYD_DEFAULT_BODY` and the
    preset bodies un-wrapped), and an operator may open the page and
    save without editing.
    """
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


# Vetted, built-in prompt bodies the admin editor seeds verbatim: every
# `AssistantType` persona body plus the default post-answering template.
# Submitting one unchanged must ALWAYS persist -- a built-in default can
# never be rejected by the classifier (BUG-0084). Compared after
# `_normalize_prompt` on both sides.
_KNOWN_BUILTIN_PROMPTS: frozenset[str] = frozenset(
    _normalize_prompt(prompt)
    for prompt in (
        *(body_for(assistant_type) for assistant_type in AssistantType),
        DEFAULT_POST_ANSWERING_PROMPT,
    )
)


class ConfigResolutionError(Exception):
    """Effective configuration is invalid or self-contradictory.

    Raised by ``resolve_effective_config`` -- the single choke point
    where every admin override is overlaid on the env / code defaults
    -- when the resulting effective configuration cannot be served
    (for example, two settings whose effective values are mutually
    exclusive).

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
        "ai_assistant_type": DEFAULT_ASSISTANT_TYPE,
        "post_answering_prompt": DEFAULT_POST_ANSWERING_PROMPT,
        "post_answering_enabled": False,
        "post_answering_filter_message": DEFAULT_POST_ANSWERING_FILTER_MESSAGE,
    }
    if overrides is not None:
        for name in values:
            override_value = getattr(overrides, name)
            # `None` means 'not overridden, fall through to the default'
            # (RuntimeConfig stores the mutable subset as `T | None`);
            # only non-None values overlay the env / code default.
            if override_value is not None:
                values[name] = override_value

    # The persisted `cwyd_agent_instructions` override is stored raw
    # (un-wrapped). Re-resolve it through the shared composition seam so
    # the fixed `CWYD_GUARDRAIL` always bookends an operator-authored
    # persona on the runtime path that consumes this value: the
    # `langgraph` orchestrator injects `effective.cwyd_agent_instructions`
    # directly as its system prompt, where an un-wrapped override would
    # drop the non-negotiable safety / out-of-domain / citation rules.
    # The `agent_framework` path wraps independently in
    # `_resolve_definition`; both resolve through
    # `resolve_cwyd_instructions`, and the no-override case is
    # byte-identical to the `CWYD_AGENT.instructions` default. The admin
    # `/config/effective` view does not use this helper -- it surfaces
    # the raw authored override by design.
    values["cwyd_agent_instructions"] = resolve_cwyd_instructions(
        overrides.cwyd_agent_instructions if overrides is not None else None
    )

    return AdminConfig(**values)


async def validate_prompt_with_rai(
    text: str,
    agents: BaseAgentsProvider,
    db: BaseDatabaseClient,
) -> str | None:
    """Review an operator-authored prompt; return rejection reason or
    ``None`` when accepted.

    Returns ``None`` for accepted prompts and a single-sentence
    operator-facing reason string when the prompt is blocked.

    Acceptance has three tiers:

    1. Empty / whitespace-only input is a no-op (revert to default) --
       accepted without a Foundry round-trip.
    2. A vetted built-in body (the default persona, any preset persona,
       or the default post-answering template -- the strings the admin
       editor seeds raw) is accepted deterministically, so an operator
       who opens the page and saves an unedited default can never be
       rejected (BUG-0084).
    3. Any other (custom) prompt is reviewed by `PROMPT_REVIEW_AGENT`,
       a classifier calibrated to review operator-authored *system
       prompts* -- it allows legitimate persona / guardrail / refusal
       language and blocks only a prompt that directs the assistant to
       behave harmfully. This is distinct from `RAI_AGENT`, which
       screens untrusted end-user chat input; applying that user-message
       classifier to a system prompt false-positived on the default
       itself.

    A FALSE verdict, a failed run, or no parseable verdict returns the
    rejection reason (fail-closed -- mirrors `rai_check`'s contract).
    The reason string is a constant so callers can rely on its shape
    for UI surfacing.
    """
    if not text or not text.strip():
        return None

    if _normalize_prompt(text) in _KNOWN_BUILTIN_PROMPTS:
        return None

    try:
        accepted = await rai_check(text, agents, db, agent=PROMPT_REVIEW_AGENT)
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
