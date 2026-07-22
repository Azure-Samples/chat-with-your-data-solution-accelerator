"""Live conversation checks (integration lane).

Drives ``POST /api/conversation`` against the real orchestrator + real
Foundry IQ / Azure Search over the in-process app boot (see
``conftest.live_app``). Assertions check behavioral invariants -- grounded
content, citation presence, the fixed out-of-domain fallback, and the SSE
channel set -- never environment-specific values (Hard Rule #18).

The in-domain queries assume the shipped sample benefits dataset is indexed
(``Benefit_Options.pdf`` etc.). Point them at any indexed topic by editing
the two query constants below.
"""

import json
import re

import httpx
import pytest

from backend.app import create_app
from backend.core.agents.definitions import CWYD_GUARDRAIL
from backend.core.pipelines.chat import KB_SEARCH_NARRATION
from backend.core.settings import OrchestratorName, get_settings
from backend.core.types import RuntimeConfig

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
    """Citation ids + answer text converge on the ``[docN]`` shape, not native
    KB markers.

    Regression guard: the ``agent_framework`` path grounds via
    the server-side Foundry IQ Knowledge Base, whose model emits native
    ``【N:M†source】`` markers inline in the answer and citation ids keyed by a
    raw ``mcp://searchindex/<doc-key>``. ``normalize_kb_citations`` (wired into
    the orchestrator) rewrites those inline markers to the grouping-ordered
    ``[docN]`` and renumbers the citation ids to match, so every citation id is
    ``[docN]`` and no native bracket survives into the answer text. The
    friendly *title* / *snippet* are not carried in the KB annotation (only the
        raw doc-key), so title/snippet recovery is tracked separately
        and is deliberately not asserted here.
    """
    response = await live_client.post(
        "/api/conversation", json=_user_turn(_IN_DOMAIN_QUERY)
    )

    assert response.status_code == 200, response.text
    body = response.json()
    citations = body.get("citations", [])
    assert citations, "expected the grounded answer to carry citations"
    unnormalized = [
        c.get("id") for c in citations if not _DOCN_PATTERN.match(c.get("id", ""))
    ]
    assert not unnormalized, f"non-[docN] citation ids observed: {unnormalized}"
    # No native KB marker (full-width brackets / dagger) survives into the
    # answer text -- inline references render as [docN], same as langgraph.
    content = body.get("content", "")
    assert "【" not in content and "†" not in content and "】" not in content, content


@pytest.mark.parametrize(
    "orchestrator_name",
    [OrchestratorName.LANGGRAPH, OrchestratorName.AGENT_FRAMEWORK],
)
async def test_reasoning_feed_streams_substantive_model_reasoning(
    require_cosmos: None,
    collect_sse,
    orchestrator_name: OrchestratorName,
) -> None:
    """BOTH orchestrators stream substantive model reasoning beyond the
    canned KB narration -- with no configuration knob.

    Honest live gate for the reasoning feed: the plumbing was
    always wired, but no substantive content reached the thinking panel
    because the answer model was never asked for a reasoning summary.
    Each orchestrator now auto-detects whether the answer deployment
    emits reasoning (``llm.supports_reasoning()``, a cached one-shot
    Responses-API probe) and, when it does, surfaces real reasoning
    frames on *each* path -- a ``reasoning`` frame whose content is
    non-empty and is not the fixed ``KB_SEARCH_NARRATION``:

      * ``langgraph`` routes ``complete()`` -> ``reason()`` -> the
        Responses API with a reasoning summary requested.
      * ``agent_framework`` sets a Responses-API ``reasoning`` option on
        ``agent.run(...)``, surfaced as ``text_reasoning`` content on the
        reasoning channel.

    The effective orchestrator is forced past any persisted cosmos admin
    override by writing ``app.state.runtime_overrides`` after boot: the
    request-time ``get_runtime_overrides`` reads that attribute and
    ``resolve_effective_config`` overlays the non-``None``
    ``orchestrator_name``, so each path is exercised deterministically
    regardless of what the live deployment has saved. ``require_cosmos``
    gates the lane to the cosmosdb + Azure Search setup where
    ``agent_framework`` (Foundry IQ Knowledge Base) is a valid pairing.
    The autouse env fixture restores the settings cache on teardown.
    """
    get_settings.cache_clear()

    app = create_app()
    async with app.router.lifespan_context(app):
        # Force the effective orchestrator deterministically: overwrite
        # the cosmos-loaded overrides so `resolve_effective_config`
        # resolves to the parametrized name on this request.
        app.state.runtime_overrides = RuntimeConfig(orchestrator_name=orchestrator_name)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://integration"
        ) as client:
            events = await collect_sse(
                client,
                "/api/conversation",
                json_body=_user_turn(_IN_DOMAIN_QUERY),
            )

    assert "error" not in {event.event for event in events}, [
        event.data for event in events if event.event == "error"
    ]
    reasoning_contents = [
        json.loads(event.data).get("content", "")
        for event in events
        if event.event == "reasoning"
    ]
    assert (
        reasoning_contents
    ), f"[{orchestrator_name}] expected at least one reasoning frame"
    substantive = [
        text
        for text in reasoning_contents
        if text.strip() and text.strip() != KB_SEARCH_NARRATION
    ]
    assert substantive, (
        f"[{orchestrator_name}] expected substantive model reasoning beyond "
        f"the canned KB narration; saw only: {reasoning_contents}"
    )
