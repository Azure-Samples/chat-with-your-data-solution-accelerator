"""Tests for ``backend.services.admin``.

Pillar: Stable Core
Phase: 5 (admin surface helpers)
"""

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

from backend.core.agents.definitions import CWYD_AGENT
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
    assert effective.post_answering_prompt == ""
    assert effective.post_answering_enabled is False
    assert effective.post_answering_filter_message == ""


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
    # Overridden:
    assert effective.orchestrator_name == "agent_framework"
    assert effective.cwyd_agent_instructions == "You are a pirate."
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
    assert effective.cwyd_agent_instructions == "Custom prompt."
    assert effective.post_answering_prompt == "Is this grounded?"
    assert effective.post_answering_enabled is True
    assert effective.post_answering_filter_message == "Filtered."


def test_resolve_effective_config_false_boolean_override_is_honored() -> None:
    """A ``False`` override on a boolean whose env default is ``True``
    is applied (``None`` vs ``False`` are distinct)."""
    settings = _settings(search_use_semantic_search=True)
    overrides = RuntimeConfig(search_use_semantic_search=False)
    effective = resolve_effective_config(settings, overrides)
    assert effective.search_use_semantic_search is False
