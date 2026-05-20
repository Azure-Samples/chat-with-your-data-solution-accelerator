# ADR 0004 — Foundry IQ via `AIProjectClient` + `AsyncOpenAI` — no `openai` SDK import in v2

- **Status**: Accepted
- **Date**: 2026-04-23
- **Phase**: 2 (task #12)
- **Pillar**: Stable Core
- **Deciders**: CWYD v2 maintainers

## Context

CWYD v1 calls Azure OpenAI directly:

```python
from openai import AzureOpenAI
client = AzureOpenAI(
    azure_endpoint=env_helper.AZURE_OPENAI_ENDPOINT,
    api_key=env_helper.AZURE_OPENAI_API_KEY,
    api_version=env_helper.AZURE_OPENAI_API_VERSION,
)
```

This pattern is everywhere in v1's orchestrators, search handlers, and tools. It has three problems v2 needs to solve at the same time:

1. **Per-deployment endpoints and per-deployment keys** — every model deployment is a separate URL + key. Scaling to o-series reasoning + GPT-* + embeddings means three sets of credentials and three places to rotate them.
2. **API-key auth coupled to Key Vault** — see [ADR 0002](0002-no-key-vault-uami-rbac.md). Removing Key Vault means removing `AZURE_OPENAI_API_KEY` first.
3. **No central place to plug in agent infrastructure** — Foundry features (Knowledge Base, Agent Framework, evaluation, content safety integration) live behind `AIProjectClient`, not behind the raw OpenAI SDK. Importing `openai` directly skips the substrate that Phase 3+ depends on.

Hard Rule #7 in [`copilot-instructions.md`](../../../.github/copilot-instructions.md) bans `from openai import` / `from openai.* import` anywhere under `v2/src/{shared,providers,pipelines}/**`. The challenge: we still need to **call** the OpenAI Chat Completions / Embeddings APIs (Foundry doesn't replace those wire formats — it routes them). How do we use the client object without importing its type?

## Decision

**All v2 LLM access goes through `azure.ai.projects.aio.AIProjectClient`.** The Foundry IQ provider ([`v2/src/providers/llm/foundry_iq.py`](../../src/providers/llm/foundry_iq.py)) constructs one `AIProjectClient` from the `AZURE_AI_PROJECT_ENDPOINT` Bicep output + a `DefaultAzureCredential` ([ADR 0002](0002-no-key-vault-uami-rbac.md), [ADR 0005](0005-credential-and-llm-singleton-via-lifespan.md)) and obtains the OpenAI-compatible client via:

```python
oai = self._get_project_client().get_openai_client()
response = await oai.chat.completions.create(model=deployment, messages=...)
```

The returned object **is** an `AsyncOpenAI` instance (the `azure-ai-projects` SDK builds it for us), so `oai.chat.completions.create(...)` and `oai.embeddings.create(...)` work with their native shapes. We get to keep the well-known OpenAI call surface **without** ever importing `openai` ourselves.

### Enforcement is structural, not advisory

```python
# allowed -- only `azure.ai.projects.aio` is imported
from azure.ai.projects.aio import AIProjectClient

# banned -- enforced by Hard Rule #7 + greppable
# from openai import AsyncOpenAI            # ❌
# from openai import AzureOpenAI            # ❌
# from openai.types.chat import ...         # ❌
```

The `openai` package is a transitive dependency (pulled in by `azure-ai-projects`), so it's installed — but our code never references its name. Greppable: `grep -rn "^from openai\|^import openai" v2/src/` must return zero hits.

### Single-resource topology

The provider holds **one** `AIProjectClient` per app process (created lazily on first use, closed in lifespan shutdown — see [ADR 0005](0005-credential-and-llm-singleton-via-lifespan.md)). Foundry routes per-call traffic to the right deployment based on the `model=` argument; there is no per-deployment endpoint or per-deployment client.

Deployment selection is data-driven from `AppSettings.openai`:

```python
def _resolve_deployment(self, override, *, kind):
    if override: return override
    return {
        "chat":   self._settings.openai.gpt_deployment,
        "reason": self._settings.openai.reasoning_deployment,
        "embed":  self._settings.openai.embedding_deployment,
    }[kind]
```

A missing deployment env var fails at the call site with a named error, not at the SDK level with a 404.

### Methods on `BaseLLMProvider`

`FoundryIQ` implements the four methods on [`BaseLLMProvider`](../../src/providers/llm/base.py):

| Method | Foundry call | Status |
|---|---|---|
| `chat(messages, ...)` → `ChatMessage` | `oai.chat.completions.create` | ✅ Phase 2 |
| `chat_stream(messages, ...)` → `AsyncIterator[ChatChunk]` | `oai.chat.completions.create(stream=True)` | ✅ Phase 2 |
| `embed(texts, ...)` → `EmbeddingResult` | `oai.embeddings.create` | ✅ Phase 2 |
| `reason(messages, ...)` → `AsyncIterator[OrchestratorEvent]` | o-series routing — reserved for task #25 | ⏳ ABC locked, impl raises `NotImplementedError` |

`reason()` returns the typed `OrchestratorEvent` channel directly — see [ADR 0007](0007-orchestrator-event-typed-sse-channel.md) for why it's not a string stream.

## Consequences

### Positive

- **One credential, one endpoint, one client object.** Routing GPT-* / o-series / embeddings is a `model=` argument, not a configuration sprawl.
- **AAD-only auth.** No `AZURE_OPENAI_API_KEY` field exists in `AppSettings` — the absence is structural, not policy.
- **Foundry features (Knowledge Base, Agent Framework, evaluations) sit on the same client** and are reachable from the same provider without re-plumbing credentials.
- **Hard Rule #7 is greppable** — no `openai` import in `v2/src/` is checkable in CI / code review.
- **Test seam for free**: the constructor accepts a `project_client` override, so tests inject a fake `AIProjectClient` whose `get_openai_client()` returns a `MagicMock`. No HTTP, no creds.

### Negative

- **`openai` is still installed transitively.** A determined contributor could `import openai`. The defense is the lint rule and code review — we accept this at the cost of not vendoring `azure-ai-projects`'s entire dependency tree.
- **Object types we receive (`oai`, response objects) come from the `openai` package** but we never name them in annotations. Type hints fall back to `Any` at the call sites that hold the OpenAI client. Acceptable: the call surface is small (`chat.completions.create`, `embeddings.create`), well-known, and covered by tests.
- **Provider depends on `azure-ai-projects` aio surface**, which is a relatively young SDK. We pin a working minor version and re-validate on each bump.

### Neutral

- **Streaming uses `stream=True` on the OpenAI call surface**, not a Foundry-specific streaming API. Whatever Foundry adds later (server-side reasoning trace events, tool-call deltas) plugs into `chat_stream` / `reason` without changing the call sites.

## Alternatives considered

1. **Use `from openai import AsyncAzureOpenAI` directly with AAD auth** (`azure_ad_token_provider=...`). Rejected: keeps the per-deployment endpoint problem, bypasses the Foundry substrate, and re-introduces the `openai` import we want banned. We'd lose Knowledge Base, Agent Framework, evaluation hooks.
2. **Wrap the `openai` SDK in our own thin client and forbid the import everywhere except that wrapper.** Rejected: builds a private fork of an SDK surface we don't control, and the wrapper would re-export types we said we wouldn't import. The Foundry-managed `get_openai_client()` already gives us what we'd build.
3. **Foundry HTTP REST directly via `aiohttp`.** Rejected: re-implements Chat Completions / Embeddings serialization, streaming SSE parsing, retry logic, and tool-call shapes — all already correct in the `openai` client that `azure-ai-projects` hands us.
4. **Use `azure-ai-inference` instead of `azure-ai-projects`.** Rejected for now: `inference` is a thinner inference-only surface that doesn't expose Knowledge Base / Agent Framework. We need the project-scoped client for Phase 3+. Re-evaluate if Foundry IQ unifies the two surfaces.

## References

- [`v2/src/providers/llm/foundry_iq.py`](../../src/providers/llm/foundry_iq.py) — the only place `AIProjectClient` is constructed.
- [`v2/src/providers/llm/base.py`](../../src/providers/llm/base.py) — `BaseLLMProvider` ABC: `chat`, `chat_stream`, `embed`, `reason`, `aclose`.
- [`v2/tests/providers/llm/test_foundry_iq.py`](../../tests/providers/llm/test_foundry_iq.py) — 11 tests with injected fake `AIProjectClient`.
- [`copilot-instructions.md` Hard Rule #7](../../../.github/copilot-instructions.md) — bans `openai` SDK import in v2.
- [ADR 0001](0001-registry-over-factory-dispatch.md) — `llm` is a registry domain; `foundry_iq` is one provider.
- [ADR 0002](0002-no-key-vault-uami-rbac.md) — why no API key.
- [ADR 0005](0005-credential-and-llm-singleton-via-lifespan.md) — single client lifecycle.
- [ADR 0007](0007-orchestrator-event-typed-sse-channel.md) — why `reason()` returns `OrchestratorEvent`, not a string.
- [`development_plan.md` §2.1 + §4 Phase 2 task #12](../development_plan.md) — removal entry + Phase 2 task.
- `azure-ai-projects` Python SDK: <https://learn.microsoft.com/python/api/overview/azure/ai-projects-readme>.
