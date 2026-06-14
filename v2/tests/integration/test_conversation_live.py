"""Live conversation checks (integration lane).

Pillar: Stable Core
Phase: 6

Drives ``POST /api/conversation`` against the real orchestrator + real
Foundry IQ / Azure Search over the in-process app boot (see
``conftest.live_app``). Assertions check behavioral invariants -- grounded
content, citation presence, the fixed out-of-domain fallback, and the SSE
channel set -- never environment-specific values (Hard Rule #18).

The in-domain queries assume the shipped sample benefits dataset is indexed
(``Benefit_Options.pdf`` etc.). Point them at any indexed topic by editing
the two query constants below.
"""

import re

import httpx
import pytest

from backend.core.agents.definitions import CWYD_GUARDRAIL

pytestmark = pytest.mark.integration

# A question the shipped sample dataset (employee benefits) can ground.
_IN_DOMAIN_QUERY = "What health plans are available?"

# A question no benefits document can answer -> the fixed out-of-domain path.
_OUT_OF_DOMAIN_QUERY = "What is the capital of France?"

# Marker substring of the fixed out-of-domain reply. Sourced from the
# guardrail rather than hardcoded: the self-check below fails loudly if the
# canonical wording drifts, signalling the marker (and this test) needs an
# update instead of silently passing on a stale phrase.
_FALLBACK_MARKER = "not available in the retrieved data"

# Normalized citation id shape every orchestrator should converge on.
_DOCN_PATTERN = re.compile(r"^\[doc\d+\]$")


def _user_turn(query: str) -> dict[str, object]:
    """Build a single-user-turn conversation request body."""
    return {"messages": [{"role": "user", "content": query}]}


async def test_in_domain_query_grounds_with_citations(
    live_client: httpx.AsyncClient,
) -> None:
    """A grounded question returns non-empty content and at least one citation."""
    response = await live_client.post(
        "/api/conversation", json=_user_turn(_IN_DOMAIN_QUERY)
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body.get("content", "").strip(), "expected a non-empty grounded answer"
    citations = body.get("citations", [])
    assert citations, "expected the grounded answer to carry citations"
    assert all(c.get("id", "").strip() for c in citations), citations


async def test_out_of_domain_query_returns_fixed_fallback(
    live_client: httpx.AsyncClient,
) -> None:
    """An out-of-domain question returns the fixed fallback and no citations."""
    # Source anchor: the marker must still be the canonical guardrail wording.
    assert _FALLBACK_MARKER in CWYD_GUARDRAIL.lower()

    response = await live_client.post(
        "/api/conversation", json=_user_turn(_OUT_OF_DOMAIN_QUERY)
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert _FALLBACK_MARKER in body.get("content", "").lower(), body.get("content")
    assert body.get("citations") == [], body.get("citations")


async def test_in_domain_query_streams_answer_and_citation_channels(
    live_client: httpx.AsyncClient,
    collect_sse,
) -> None:
    """The SSE stream emits the answer + citation channels with no error event."""
    events = await collect_sse(
        live_client, "/api/conversation", json_body=_user_turn(_IN_DOMAIN_QUERY)
    )

    channels = {event.event for event in events}
    assert "answer" in channels, channels
    assert "citation" in channels, channels
    assert "error" not in channels, [e for e in events if e.event == "error"]
    answer_payloads = [event.data for event in events if event.event == "answer"]
    assert any(payload.strip() for payload in answer_payloads), answer_payloads


async def test_in_domain_citation_ids_use_normalized_docn_shape(
    live_client: httpx.AsyncClient,
    require_agent_framework: None,
) -> None:
    """Citations expose the normalized ``[docN]`` id, not native KB markers.

    Regression guard for BUG-0030: the ``agent_framework`` path grounds via
    the server-side Foundry IQ Knowledge Base, and the live deployment now
    surfaces annotations whose ``file_id`` is the ``[docN]`` marker and whose
    ``title`` is the friendly filename, so ``citations_from_annotations``
    passes the normalized shape straight through. If a future Foundry IQ /
    SDK change regresses to native ``【N:M†source】`` markers or raw
    ``mcp://searchindex/<doc-key>`` ids, this assertion fails and the message
    captures the offending id/title pairs.
    """
    response = await live_client.post(
        "/api/conversation", json=_user_turn(_IN_DOMAIN_QUERY)
    )

    assert response.status_code == 200, response.text
    citations = response.json().get("citations", [])
    assert citations, "expected the grounded answer to carry citations"
    unnormalized = [
        (c.get("id"), c.get("title"))
        for c in citations
        if not _DOCN_PATTERN.match(c.get("id", ""))
        or c.get("title", "").startswith("mcp://")
    ]
    assert not unnormalized, f"non-normalized citations observed: {unnormalized}"
