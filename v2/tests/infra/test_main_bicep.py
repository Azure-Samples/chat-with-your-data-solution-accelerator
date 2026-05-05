"""Pillar: Stable Core / Phase: 4 (CU-001e) — Bicep regression tests.

The full Bicep contract is validated by `az bicep build` (run as the
last step of CU-001e); these grep-style guards catch *symbol-level*
regressions fast (no Bicep CLI required) so a stray rename or
whitespace edit can't silently drop the agent_id wiring.

Naming convention enforced (per Hard Rule #11): Bicep param =
`camelCase` (`azureAiAgentId`); env var on the container app =
`UPPER_SNAKE_CASE` (`AZURE_AI_AGENT_ID`).
"""
from __future__ import annotations

from pathlib import Path

import pytest


_BICEP = (
    Path(__file__).resolve().parents[2] / "infra" / "main.bicep"
)


@pytest.fixture(scope="module")
def bicep_text() -> str:
    return _BICEP.read_text(encoding="utf-8")


def test_bicep_declares_azure_ai_agent_id_param(bicep_text: str) -> None:
    """`azureAiAgentId` is exposed as an optional Bicep parameter so
    operators can pin a specific Foundry agent post-deployment without
    re-templating.

    Default is the empty string -- the runtime validator
    (`OrchestratorSettings._require_agent_id_for_agent_framework`,
    CU-001a) raises only when the orchestrator is actually switched to
    `agent_framework`. This keeps the WAF-aligned default deployment
    (LangGraph orchestrator) green even if no agent has been created
    in Foundry yet.
    """
    assert "param azureAiAgentId string" in bicep_text
    # Default must be the empty string. Accept either single or double
    # quotes (Bicep idiom is single-quote, but both parse).
    assert (
        "param azureAiAgentId string = ''" in bicep_text
        or 'param azureAiAgentId string = ""' in bicep_text
    )


def test_backend_container_env_exposes_agent_id(bicep_text: str) -> None:
    """The backend Container App must expose `AZURE_AI_AGENT_ID` as an
    environment variable bound to the `azureAiAgentId` Bicep parameter.

    This is the canonical env name read by `OrchestratorSettings.agent_id`
    via its first `validation_alias` choice (CU-001a). Without this
    binding the Bicep parameter would be inert.
    """
    # Match either dictionary-literal style ACA SDK accepts; we keep
    # the assertion narrow to (a) the env-var name and (b) that the
    # value resolves to the Bicep param (not a hard-coded literal).
    assert "'AZURE_AI_AGENT_ID'" in bicep_text
    # The env entry must reference the param, not embed a literal.
    # Tolerate any whitespace between `value:` and `azureAiAgentId`.
    import re

    pattern = re.compile(
        r"name:\s*'AZURE_AI_AGENT_ID'\s*,?\s*value:\s*azureAiAgentId\b"
    )
    assert pattern.search(bicep_text), (
        "AZURE_AI_AGENT_ID env entry must bind to the azureAiAgentId param "
        "(no literals; no string interpolation)."
    )
