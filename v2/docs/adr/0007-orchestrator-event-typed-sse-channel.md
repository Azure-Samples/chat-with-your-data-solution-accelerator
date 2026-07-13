# ADR 0007 — `OrchestratorEvent` typed SSE channel — `reasoning` separate from `answer`

- **Status**: Accepted
- **Date**: 2026-04-26
- **Phase**: 2 (post-build review fix; locks the contract before Phase 3)
- **Pillar**: Stable Core
- **Deciders**: CWYD v2 maintainers

## Context

CWYD v2 must surface intermediate model output — chain-of-thought from o-series reasoning models, tool invocations from LangGraph / Agent Framework, retrieved citations, and per-token answer deltas — to the React frontend in real time. The frontend renders these in distinct UI surfaces: a collapsible "Reasoning" panel, a "Tool calls" tray, the main answer pane, an inline citations strip, and an error banner.

CWYD v1 collapses the same surface into a single string stream:

```python
yield json.dumps({"role": "assistant", "content": delta})
```

Reasoning text, tool call JSON, and the final answer all flow through `content`. The frontend has to **string-match** to tell them apart (`if delta.startswith("[Tool]")`, `if "<reasoning>" in delta`). This is fragile, leaks model-specific markup into the UI layer, and makes server-side composition (e.g., interleaving a tool-call event between two answer tokens) impossible without renegotiating the marker syntax.

The first cut of `BaseLLMProvider.reason()` in Phase 2 had a placeholder signature:

```python
async def reason(self, messages, *, deployment=None) -> AsyncIterator[str]: ...
```

That would have shipped the v1 problem into v2 verbatim. The post-build review caught it (drift D5) and required a typed channel before any orchestrator or SSE pipeline lands in Phase 3 — once a producer commits to a wire shape, every downstream consumer hardcodes it.

The MACAE multi-agent sample uses a typed event bus (`AgentMessage` with discriminated kinds). CGSA uses a simpler `{type, data}` envelope. We need something close to MACAE's discipline but small enough to fit Phase 3's Stable Core.

## Decision

**The reasoning feed is a stream of typed `OrchestratorEvent` objects on a fixed set of channels.** Defined once in [`v2/src/shared/types.py`](../../src/shared/types.py); consumed everywhere via `AsyncIterator[OrchestratorEvent]`.

### Event shape

```python
OrchestratorChannel = Literal["reasoning", "tool", "answer", "citation", "error"]

class OrchestratorEvent(BaseModel):
    channel: OrchestratorChannel
    content: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
```

### The five channels (closed set)

| Channel | Purpose | Frontend surface | Producer examples |
|---|---|---|---|
| `reasoning` | Chain-of-thought / scratchpad / o-series reasoning trace. | Collapsible "Reasoning" panel. | `FoundryIQ.reason()`, LangGraph node introspection. |
| `tool` | Tool invocation, tool result. | "Tool calls" tray. | LangGraph `ToolNode`, Agent Framework tool-call events. |
| `answer` | The user-facing response, token by token. | Main answer pane. | All orchestrators. |
| `citation` | A document or chunk reference for grounding. | Inline citations strip. | Search providers via the orchestrator. |
| `error` | A handled error worth surfacing to the user. | Error banner. | All producers. |

The channel set is **closed**. Adding a sixth channel is a breaking change to public consumers (per Hard Rule #11 — public API names need user confirmation to change once shipped) and requires a superseding ADR.

### Producer contract

Every producer that yields onto the SSE feed yields `OrchestratorEvent`:

- `BaseLLMProvider.reason()` returns `AsyncIterator[OrchestratorEvent]` ([ADR 0004](0004-foundry-iq-no-openai-sdk-import.md)).
- `OrchestratorBase.run()` (Phase 3) returns `AsyncIterator[OrchestratorEvent]`.
- The chat pipeline ([`v2/src/pipelines/chat.py`](../../src/pipelines/chat.py), Phase 3) yields `OrchestratorEvent` and serializes it once at the SSE boundary.

There is no parallel "reasoning string" channel. Reasoning text goes on `channel="reasoning"`. Answer tokens go on `channel="answer"`. **Reasoning never leaks into the answer string** — that's the whole point.

### Wire format (Phase 3 task #22)

The SSE handler in `routers/conversation.py` will serialize each event as:

```
event: reasoning
data: {"content": "...", "metadata": {}}

event: answer
data: {"content": "Hello"}
```

`event:` carries `OrchestratorChannel`, `data:` carries `model_dump_json(exclude={"channel"})`. Frontend `EventSource` consumers attach handlers per `event:` type — no string-matching, no client-side discrimination logic.

### Why `metadata` is `dict[str, Any]`

Per-channel structured detail (tool name + arguments, citation document_id + score, error code + traceback) varies by channel. We considered modeling each channel as a separate Pydantic class with a discriminated union — it's stricter but doubles the type surface and makes adding a metadata key a 5-file change. The `dict[str, Any]` shape gives producers room to attach what they need; consumers that care about shape (e.g., the citations strip) validate on read with their own Pydantic model. Acceptable looseness for v2's first iteration; can be tightened in a future ADR if drift becomes a problem.

## Consequences

### Positive

- **The frontend never string-matches.** Channel routing happens at the SSE event-type level, which is what `EventSource` was designed for.
- **Producers can be composed.** A pipeline can interleave `reasoning` from FoundryIQ, `tool` from LangGraph, `citation` from search, and `answer` tokens from the same model — all without renegotiating the wire shape.
- **`reason()` and `run()` share a return type**, so an orchestrator can delegate directly to the LLM's reasoning stream and forward events unchanged.
- **One contract, five channels, locked at Phase 2.** Every Phase 3+ producer ships against the same shape. No drift between FoundryIQ's reasoning emission and Agent Framework's reasoning emission.
- **Test seam is trivial.** `assert events[0].channel == "reasoning"` rather than parsing strings.

### Negative

- **`metadata: dict[str, Any]` is loose.** A producer can typo a metadata key (e.g., `documentid` vs `document_id`) and consumers won't notice until render time. Mitigated by per-consumer Pydantic re-parsing where shape matters; revisit if drift accumulates.
- **`OrchestratorChannel` is a closed `Literal`.** Adding a channel requires touching every place that exhaustively switches on it (today: zero places; Phase 3 frontend: one router). Closed is the point — it's the source of the discipline — but it's a real constraint.
- **Reasoning and answer in the same stream means the frontend must demux.** That's deliberate: the frontend already has to render both surfaces, and demuxing by `event:` type is what `EventSource` does for free.

### Neutral

- **Channel `error` is for *handled* errors that the user should see**, not for HTTP-level failures. A 500 still goes via the response status code; `error` is for "the orchestrator failed to call a tool, here's a degraded explanation."
- **No `done` channel.** End of stream is signaled by the SSE connection closing, which `EventSource` exposes natively. Adding a `done` channel would duplicate that signal.

## Alternatives considered

1. **`AsyncIterator[str]` (the v1 shape).** Rejected: this is the bug we're fixing. Forces the frontend to string-match; can't carry tool-call structure without inventing markup.
2. **Discriminated union of 5 Pydantic classes** (`ReasoningEvent`, `ToolEvent`, etc.) instead of one `OrchestratorEvent` with a `channel` field. Rejected for now: stricter but doubles class count, and `model_dump_json` discrimination would force every consumer to switch on `__class__` (or `Literal` discriminator). The single-class shape is enough for Phase 3; revisit if `metadata` shape drift becomes a real problem.
3. **Borrow MACAE's `AgentMessage` shape verbatim.** Rejected: MACAE carries multi-agent sender/receiver routing that CWYD doesn't need yet. Adopting the shape now would force fields we don't populate, blurring the contract.
4. **Use OpenTelemetry spans as the reasoning channel.** Rejected: spans serve a different consumer (tracing backends, not browsers), and we don't want to pin frontend rendering to OTel SDK availability.
5. **Server-Sent Events with a single `data:` field carrying typed JSON.** Rejected: the `event:` field is exactly what discriminated SSE was designed for; clients (`EventSource`) handle it natively; using only `data:` would push discrimination back into the consumer.

## References

- [`v2/src/shared/types.py`](../../src/shared/types.py) — `OrchestratorChannel` Literal + `OrchestratorEvent` model.
- [`v2/src/providers/llm/base.py`](../../src/providers/llm/base.py) — `BaseLLMProvider.reason() -> AsyncIterator[OrchestratorEvent]`.
- [`v2/src/providers/llm/foundry_iq.py`](../../src/providers/llm/foundry_iq.py) — async-generator stub raising `NotImplementedError("task #25")`.
- [`v2/tests/providers/llm/test_foundry_iq.py`](../../tests/providers/llm/test_foundry_iq.py) — consumes the iterator to confirm the async-generator pattern.
- [ADR 0004](0004-foundry-iq-no-openai-sdk-import.md) — `reason()` is the o-series surface on FoundryIQ.
- [`copilot-instructions.md` Hard Rule #6 + #11](../../../.github/copilot-instructions.md) — reasoning channels listed; renames to public API names need confirmation.
- [`development_plan.md` §0 + Phase 3 task #17, #25](../development_plan.md) — orchestrator base + o-series routing tasks consume this contract.
- MACAE multi-agent message bus pattern (read-only reference): <https://github.com/microsoft/Multi-Agent-Custom-Automation-Engine-Solution-Accelerator>.
- CGSA reasoning visualization patterns (read-only reference): <https://github.com/microsoft/content-generation-solution-accelerator>.
