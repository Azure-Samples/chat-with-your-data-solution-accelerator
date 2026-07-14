"""Tests for ``backend.services.admin``."""

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

from backend.core.agents.definitions import (
    CWYD_AGENT,
    CWYD_GUARDRAIL,
    compose_cwyd_instructions,
    resolve_cwyd_instructions,
)
from backend.core.agents.presets import (
    DEFAULT_ASSISTANT_TYPE,
    DEFAULT_POST_ANSWERING_FILTER_MESSAGE,
    DEFAULT_POST_ANSWERING_PROMPT,
)
from backend.core.types import RuntimeConfig
from backend.models.admin import AdminConfig
from backend.services.admin import (
    ConfigResolutionError,
    host_only,
    resolve_effective_config,
    utcnow_iso,
)


def test_utcnow_iso_returns_iso8601_with_utc_offset() -> None:
    value = utcnow_iso()
    parsed = datetime.fromisoformat(value)
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == UTC.utcoffset(parsed)


def test_utcnow_iso_is_monotonic_non_decreasing() -> None:
    first = datetime.fromisoformat(utcnow_iso())
    second = datetime.fromisoformat(utcnow_iso())
    assert second >= first


def test_host_only_returns_empty_string_for_empty_input() -> None:
    assert host_only("") == ""


def test_host_only_extracts_netloc_from_full_url() -> None:
    assert (
        host_only("https://my-foundry.eastus.api.azureml.ms/projects/p1?x=1")
        == "my-foundry.eastus.api.azureml.ms"
    )


def test_host_only_strips_path_and_query() -> None:
    result = host_only("https://example.com/tenant/abc?token=secret")
    assert "/tenant/abc" not in result
    assert "token" not in result
    assert result == "example.com"


# ---------------------------------------------------------------------------
# ConfigResolutionError
# ---------------------------------------------------------------------------


def test_config_resolution_error_is_an_exception() -> None:
    """The app-level handler registers against an ``Exception`` subclass;
    if this regressed to a plain object the handler would never fire."""
    assert issubclass(ConfigResolutionError, Exception)


def test_config_resolution_error_exposes_message_reason_and_context() -> None:
    """The 409 body reads ``str(exc)`` + ``exc.reason``; the telemetry
    record reads ``exc.reason`` + ``exc.context``. All three must be
    addressable as documented."""
    exc = ConfigResolutionError(
        "agent_framework needs an Azure AI Search index.",
        reason="orchestrator_requires_azure_search",
        context={
            "index_store": "pgvector",
            "configured_orchestrator": "agent_framework",
        },
    )
    assert str(exc) == "agent_framework needs an Azure AI Search index."
    assert exc.reason == "orchestrator_requires_azure_search"
    assert exc.context == {
        "index_store": "pgvector",
        "configured_orchestrator": "agent_framework",
    }


def test_config_resolution_error_context_defaults_to_empty_dict() -> None:
    """``context`` is optional -- a reason-only raise must still give the
    handler a mapping to splat into the log ``extra`` without a None
    guard."""
    exc = ConfigResolutionError("bad config", reason="some_reason")
    assert exc.context == {}


# ---------------------------------------------------------------------------
# resolve_effective_config
# ---------------------------------------------------------------------------


def _settings(
    *,
    orchestrator_name: str = "langgraph",
    openai_temperature: float = 0.0,
    openai_max_tokens: int = 1000,
    search_use_semantic_search: bool = True,
    search_top_k: int = 5,
    log_level: str = "INFO",
    content_safety_enabled: bool = False,
    index_store: str = "AzureSearch",
) -> Any:
    """Minimal ``AppSettings`` stand-in exposing only the attributes
    ``resolve_effective_config`` reads."""
    return SimpleNamespace(
        orchestrator=SimpleNamespace(name=orchestrator_name),
        openai=SimpleNamespace(
            temperature=openai_temperature,
            max_tokens=openai_max_tokens,
        ),
        search=SimpleNamespace(
            use_semantic_search=search_use_semantic_search,
            top_k=search_top_k,
        ),
        observability=SimpleNamespace(log_level=log_level),
        content_safety=SimpleNamespace(enabled=content_safety_enabled),
        database=SimpleNamespace(index_store=index_store),
    )


def test_resolve_effective_config_cold_start_returns_env_defaults() -> None:
    """No overrides -> every field falls through to its env / code default."""
    settings = _settings(
        orchestrator_name="langgraph",
        openai_temperature=0.3,
        openai_max_tokens=800,
        search_use_semantic_search=True,
        search_top_k=7,
        log_level="WARNING",
        content_safety_enabled=True,
    )
    effective = resolve_effective_config(settings, None)
    assert isinstance(effective, AdminConfig)
    assert effective.orchestrator_name == "langgraph"
    assert effective.openai_temperature == 0.3
    assert effective.openai_max_tokens == 800
    assert effective.search_use_semantic_search is True
    assert effective.search_top_k == 7
    assert effective.log_level == "WARNING"
    assert effective.content_safety_enabled is True
    # Prompt fields have code-constant defaults (no env source).
    assert effective.cwyd_agent_instructions == CWYD_AGENT.instructions
    assert effective.ai_assistant_type is DEFAULT_ASSISTANT_TYPE
    assert effective.post_answering_prompt == DEFAULT_POST_ANSWERING_PROMPT
    assert effective.post_answering_enabled is False
    assert (
        effective.post_answering_filter_message == DEFAULT_POST_ANSWERING_FILTER_MESSAGE
    )


def test_resolve_effective_config_all_none_overrides_match_cold_start() -> None:
    """A persisted row with every field cleared (``None``) is treated
    identically to 'no override' -- the env defaults win."""
    settings = _settings(orchestrator_name="agent_framework", search_top_k=9)
    cold = resolve_effective_config(settings, None)
    cleared = resolve_effective_config(settings, RuntimeConfig())
    assert cleared == cold


def test_resolve_effective_config_partial_overlay_keeps_env_for_unset() -> None:
    """Only the overridden fields change; unset fields keep env defaults."""
    settings = _settings(orchestrator_name="langgraph", search_top_k=5)
    overrides = RuntimeConfig(
        orchestrator_name="agent_framework",
        cwyd_agent_instructions="You are a pirate.",
    )
    effective = resolve_effective_config(settings, overrides)
    # Overridden -> the raw persona is guardrail-wrapped through the
    # shared composition seam (this is the runtime value, not the raw
    # author text), so it leads with the override body.
    assert effective.orchestrator_name == "agent_framework"
    assert effective.cwyd_agent_instructions == compose_cwyd_instructions(
        "You are a pirate."
    )
    assert effective.cwyd_agent_instructions.startswith("You are a pirate.")
    # Untouched -> env defaults:
    assert effective.search_top_k == 5
    assert effective.cwyd_agent_instructions != CWYD_AGENT.instructions


def test_resolve_effective_config_saved_override_wins_over_env() -> None:
    """Every field set on the override row beats the env default
    (saved-wins precedence)."""
    settings = _settings(
        orchestrator_name="langgraph",
        openai_temperature=0.0,
        openai_max_tokens=1000,
        search_use_semantic_search=True,
        search_top_k=5,
        log_level="INFO",
        content_safety_enabled=False,
    )
    overrides = RuntimeConfig(
        orchestrator_name="agent_framework",
        openai_temperature=0.9,
        openai_max_tokens=256,
        search_use_semantic_search=False,
        search_top_k=12,
        log_level="DEBUG",
        content_safety_enabled=True,
        cwyd_agent_instructions="Custom prompt.",
        post_answering_prompt="Is this grounded?",
        post_answering_enabled=True,
        post_answering_filter_message="Filtered.",
    )
    effective = resolve_effective_config(settings, overrides)
    assert effective.orchestrator_name == "agent_framework"
    assert effective.openai_temperature == 0.9
    assert effective.openai_max_tokens == 256
    assert effective.search_use_semantic_search is False
    assert effective.search_top_k == 12
    assert effective.log_level == "DEBUG"
    assert effective.content_safety_enabled is True
    assert effective.cwyd_agent_instructions == compose_cwyd_instructions(
        "Custom prompt."
    )
    assert effective.post_answering_prompt == "Is this grounded?"
    assert effective.post_answering_enabled is True
    assert effective.post_answering_filter_message == "Filtered."


def test_resolve_effective_config_wraps_instruction_override_in_guardrail() -> None:
    """The persisted persona override is surfaced guardrail-wrapped, not
    raw: the effective value leads with the operator body and ends with
    the fixed `CWYD_GUARDRAIL` exactly once. This is the runtime text the
    langgraph orchestrator injects as its system prompt, so the
    non-negotiable safety rules bookend an operator-authored persona on
    both orchestrator paths."""
    settings = _settings(orchestrator_name="langgraph")
    overrides = RuntimeConfig(cwyd_agent_instructions="Answer only in haiku.")
    effective = resolve_effective_config(settings, overrides)
    assert effective.cwyd_agent_instructions.startswith("Answer only in haiku.")
    assert effective.cwyd_agent_instructions.endswith(CWYD_GUARDRAIL)
    assert effective.cwyd_agent_instructions.count(CWYD_GUARDRAIL) == 1
    # Identical to the shared seam over the same body -- no divergent
    # wrapping between this helper and `_resolve_definition`.
    assert effective.cwyd_agent_instructions == resolve_cwyd_instructions(
        "Answer only in haiku."
    )


def test_resolve_effective_config_blank_instruction_override_falls_back() -> None:
    """A whitespace-only persona override is treated as 'cleared' and
    resolves to the wrapped default, identical to the no-override
    cold-start value."""
    settings = _settings(orchestrator_name="langgraph")
    overrides = RuntimeConfig(cwyd_agent_instructions="   ")
    effective = resolve_effective_config(settings, overrides)
    assert effective.cwyd_agent_instructions == CWYD_AGENT.instructions


def test_resolve_effective_config_false_boolean_override_is_honored() -> None:
    """A ``False`` override on a boolean whose env default is ``True``
    is applied (``None`` vs ``False`` are distinct)."""
    settings = _settings(search_use_semantic_search=True)
    overrides = RuntimeConfig(search_use_semantic_search=False)
    effective = resolve_effective_config(settings, overrides)
    assert effective.search_use_semantic_search is False


# ---------------------------------------------------------------------------
# resolve_effective_config -- orchestrator / index-store coherence (ADR 0027).
#
# Both orchestrators ground on either index store: langgraph and
# agent_framework each run app-side RAG over pgvector, and agent_framework
# additionally grounds on a Foundry IQ Knowledge Base when an Azure AI
# Search index is present. So every orchestrator / index-store pairing is
# served -- the resolver returns the effective config with no raise. (ADR
# 0027 supersedes the ADR 0022 pgvector + agent_framework block; the
# general ConfigResolutionError -> 409 mechanism is retained for any future
# incompatible effective configuration.)
# ---------------------------------------------------------------------------


def test_resolve_allows_pgvector_with_agent_framework() -> None:
    """pgvector + the agent_framework env default resolves with no raise:
    agent_framework now grounds app-side on pgvector (ADR 0027 supersedes
    the ADR 0022 block), so the pairing is served."""
    settings = _settings(orchestrator_name="agent_framework", index_store="pgvector")
    effective = resolve_effective_config(settings, None)
    assert effective.orchestrator_name == "agent_framework"


def test_resolve_allows_azure_search_with_agent_framework() -> None:
    """AzureSearch + agent_framework is the supported cloud default --
    the resolver returns the effective config with no raise."""
    settings = _settings(orchestrator_name="agent_framework", index_store="AzureSearch")
    effective = resolve_effective_config(settings, None)
    assert effective.orchestrator_name == "agent_framework"


def test_resolve_allows_pgvector_with_langgraph() -> None:
    """pgvector + langgraph is the supported local default -- langgraph
    owns its RAG over pgvector, so no Azure AI Search index is required."""
    settings = _settings(orchestrator_name="langgraph", index_store="pgvector")
    effective = resolve_effective_config(settings, None)
    assert effective.orchestrator_name == "langgraph"


def test_resolve_honors_override_flipping_pgvector_to_agent_framework() -> None:
    """The resolver reads the POST-override orchestrator: a pgvector
    deployment whose env default is langgraph but whose admin override
    selects agent_framework resolves to agent_framework with no raise --
    the admin switch takes effect on the next request."""
    settings = _settings(orchestrator_name="langgraph", index_store="pgvector")
    overrides = RuntimeConfig(orchestrator_name="agent_framework")
    effective = resolve_effective_config(settings, overrides)
    assert effective.orchestrator_name == "agent_framework"
