"""Pillar: Stable Core / Phase: 8 (agent_framework default + Foundry IQ Knowledge Base).

Param/output wiring guards for `modules/ai-project-search-connection.bicep`.

The module owns the Foundry Project -> Azure AI Search connection. Phase 8
makes it knowledge-base-aware: it accepts the KB name, records it on the
connection metadata, and surfaces it as an output so `main.bicep` can flow
it to the backend Container App (`AZURE_AI_SEARCH_KNOWLEDGE_BASE_NAME`) and
the agent_framework orchestrator can resolve the KB by name. These
grep-style guards pin that contract fast (no Bicep CLI required); the full
template is still validated by `az bicep build`.
"""

from pathlib import Path

import pytest


_MODULE = (
    Path(__file__).resolve().parents[2]
    / "infra"
    / "modules"
    / "ai-project-search-connection.bicep"
)


@pytest.fixture(scope="module")
def module_text() -> str:
    return _MODULE.read_text(encoding="utf-8")


def test_declares_knowledge_base_name_param(module_text: str) -> None:
    """The module accepts the KB name; default matches SearchSettings."""
    assert "param knowledgeBaseName string = 'cwyd-kb'" in module_text


def test_connection_metadata_carries_knowledge_base_name(module_text: str) -> None:
    """The CognitiveSearch connection self-documents the KB it fronts."""
    assert "KnowledgeBaseName: knowledgeBaseName" in module_text


def test_outputs_knowledge_base_name(module_text: str) -> None:
    """The KB name is surfaced for main.bicep -> backend env wiring."""
    assert "output knowledgeBaseName string = knowledgeBaseName" in module_text


def test_existing_connection_contract_intact(module_text: str) -> None:
    """Guard the params + outputs the connection already exposed."""
    assert "param searchServiceName string" in module_text
    assert "output name string = connection.name" in module_text
    assert "output resourceId string = connection.id" in module_text
