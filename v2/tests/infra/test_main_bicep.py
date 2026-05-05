"""Pillar: Stable Core / Phase: Cleanup audit batch 2 (CU-009a) — Bicep regression tests.

The full Bicep contract is validated by `az bicep build` (run as the
last step of CU-009a); these grep-style guards catch *symbol-level*
regressions fast (no Bicep CLI required) so a stray rename, copy-paste
revert, or AI-generated "helpful" re-add can't silently re-introduce
the env-only agent-id path.

CU-009a (2026-05-05) reversed CU-001e: per ADR 0008
(lazy-foundry-agent-bootstrap), the Foundry agent id is no longer an
operator-supplied env value. Agent identity is resolved lazily on
first request and persisted in the chat-history DB. Both the
`azureAiAgentId` Bicep parameter and the `AZURE_AI_AGENT_ID`
container-app env binding **must remain absent**; restoring either
re-creates the dead-config drift CU-008..CU-012 was opened to remove.
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


def test_bicep_does_not_declare_azure_ai_agent_id_param(bicep_text: str) -> None:
    """`azureAiAgentId` must NOT be declared as a Bicep parameter.

    Per ADR 0008 (lazy-foundry-agent-bootstrap), agent identity is
    resolved lazily on first request and persisted in the chat-history
    DB. Re-adding this parameter would re-introduce the dead-config
    path CU-009a was opened to remove. If you genuinely need to pin a
    specific agent post-deployment, use the registry-backed
    `agents` provider in `v2/src/shared/agents/` (CU-010a) -- not env.
    """
    assert "azureAiAgentId" not in bicep_text, (
        "azureAiAgentId Bicep param must remain absent (CU-009a reversal of "
        "CU-001e). Agent identity is now DB-backed; see ADR 0008. To pin a "
        "specific agent, use the registry-backed agents provider, not env."
    )


def test_backend_container_env_does_not_expose_agent_id(bicep_text: str) -> None:
    """The backend Container App must NOT expose `AZURE_AI_AGENT_ID`.

    CU-009a (2026-05-05) removed this env binding. The runtime resolves
    CWYD + RAI agent ids lazily on first request and caches them in the
    chat-history DB. A literal `AZURE_AI_AGENT_ID` in the container-app
    env collection would let operators set a value that the runtime
    silently ignores -- exactly the dead-config drift this CU removes.
    """
    assert "'AZURE_AI_AGENT_ID'" not in bicep_text, (
        "AZURE_AI_AGENT_ID env binding must remain absent (CU-009a reversal "
        "of CU-001e). Agent identity is now DB-backed; see ADR 0008."
    )
    assert "AZURE_AI_AGENT_ID" not in bicep_text, (
        "AZURE_AI_AGENT_ID must not appear anywhere in main.bicep -- not as "
        "an env var, not in a comment that suggests operators should set it. "
        "Use the registry-backed agents provider instead (CU-010a)."
    )
