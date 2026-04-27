---
description: "CWYD v2 shared + providers + pipelines conventions (registry primitive, settings, observability, types; LLM, embedders, parsers, search, chat history, orchestrators, credentials providers; ingestion + chat pipelines). Use when: editing v2/src/shared/**, v2/src/providers/**, or v2/src/pipelines/**; building an orchestrator; adding a tool; calling Foundry IQ; adding a search handler; adding an embedder; adding a chat history backend; defining the OrchestratorEvent contract; wiring async credentials."
applyTo: "v2/src/{shared,providers,pipelines}/**"
---

# v2 Shared / Providers / Pipelines Conventions

## Layout (binding — matches dev_plan §3.4)

```
v2/src/
  shared/        primitives only — registry.py, settings.py, types.py, observability.py
  providers/     registry-keyed plug-ins, one folder per domain:
                   credentials/  llm/  embedders/  parsers/
                   search/  chat_history/  orchestrators/
  pipelines/     composed flows — ingestion.py, chat.py (NOT pluggable)
```

`shared/` holds cross-cutting primitives only. `providers/` holds every swappable concern. `pipelines/` composes providers into flows. Do not introduce subfolders under `shared/<domain>/` for pluggable concerns — those belong under `providers/<domain>/`.

## Pluggability contract (registry-first)

The generic `Registry[T]` lives in `v2/src/shared/registry.py`. Every provider domain follows the same recipe:

```python
# v2/src/providers/<domain>/__init__.py
from shared.registry import Registry

registry: Registry[Base<Domain>] = Registry("<domain>")

from . import provider_a, provider_b   # eager-import triggers @register

def create(key: str, **kwargs) -> Base<Domain>:
    return registry.get(key)(**kwargs)
```

```python
# v2/src/providers/<domain>/provider_a.py
from . import registry

@registry.register("a")
class ProviderA(Base<Domain>): ...
```

Caller code is one line — `domain.create(settings.<key>, ...)`. **Forbidden:** `if/elif` over provider names anywhere outside a registry; lazy `import` of provider classes inside functions; module-level client instantiation.

## Stack rules

- **Foundry IQ only** for model + knowledge access. No `from openai import AzureOpenAI`.
- LangGraph for graph-based orchestration. No `langchain.agents.ZeroShotAgent` / `AgentExecutor` (legacy).
- Azure AI Agent Framework (`azure-ai-agents`) for managed-agent orchestration.
- All I/O is async. All clients are constructed via provider factories — no module-level instantiation.

## Orchestrator contract

`v2/src/providers/orchestrators/base.py` defines:

```python
class OrchestratorBase(ABC):
    @abstractmethod
    async def run(self, request: ConversationRequest) -> AsyncIterator[OrchestratorEvent]: ...
```

Every concrete orchestrator (`langgraph.py`, `agent_framework.py`):

1. Inherits `OrchestratorBase`.
2. Self-registers via `@registry.register("<key>")` against the registry exposed in `providers/orchestrators/__init__.py`.
3. Emits events on channels: `reasoning`, `tool`, `answer`, `citation`, `error`. Never inline reasoning into `answer`.
4. Pre-pipeline: content safety check on input. Post-pipeline: post-prompt formatting + content safety check on output. Both live in `v2/src/shared/tools/` (cross-cutting helpers, not registry providers).

## LLM provider (Foundry IQ)

- Class `FoundryIQ` in `v2/src/providers/llm/foundry_iq.py`, registered as `@registry.register("foundry_iq")` against `providers/llm/__init__.py`.
- Inherits `BaseLLMProvider` (`v2/src/providers/llm/base.py`).
- Methods: `chat(...)`, `chat_stream(...)`, `embed(...)`, `reason(...)` (o-series; routes to a reasoning deployment).
- Constructor takes `AppSettings` and a `TokenCredential`. Never reads env vars directly.
- `reason()` yields `OrchestratorEvent(channel="reasoning", ...)` and `OrchestratorEvent(channel="answer", ...)` separately.

## Credentials provider

- `v2/src/providers/credentials/managed_identity.py` registered as `"managed_identity"` (returns `DefaultAzureCredential`).
- `v2/src/providers/credentials/cli.py` registered as `"cli"` (returns `AzureCliCredential`).
- Selected via `AppSettings.identity.client_id` presence (deployed Managed Identity has it set) or explicit setting.
- Async: prefer `azure.identity.aio.DefaultAzureCredential` for use in async clients.

## Tool registration

- Each tool in `v2/src/shared/tools/<name>.py` exports a `Tool` instance with `name`, `description`, `args_schema` (Pydantic), `arun(...)` async method. Tools are cross-cutting helpers (content safety, post-prompt, etc.) and are referenced directly — they are not a registry domain.
- Tools are pillar-tagged in their docstring. Most are **Stable Core**; scenario-specific ones are **Scenario Pack**.

## Search providers

- `v2/src/providers/search/azure_search.py` (registered `"azure_search"`) and `v2/src/providers/search/pgvector.py` (registered `"pgvector"`) implement `BaseSearch` (`v2/src/providers/search/base.py`) with `async def search(query, top_k, filters) -> list[SearchResult]`.
- `SearchResult` is a Pydantic model in `v2/src/shared/types.py` with `id`, `content`, `score`, `metadata`.
- Selected at runtime via `search.create(settings.database.index_store, ...)`.

## Chat history providers

- `v2/src/providers/chat_history/cosmosdb.py` (registered `"cosmosdb"`) and `v2/src/providers/chat_history/postgres.py` (registered `"postgres"`) implement `BaseChatHistory` (CRUD + feedback). Async only.
- Selected at runtime via `chat_history.create(settings.database.db_type, ...)`.

## Settings

- Single root `AppSettings` in `v2/src/shared/settings.py` (Pydantic-Settings, nested per Azure service). Reads every Bicep output env var.
- Cached `get_settings()` accessor. Never read env vars directly outside this module.

## Banned

- `from openai import …` anywhere in `v2/src/{shared,providers,pipelines}/**`.
- `semantic_kernel`, `promptflow`.
- Module-level `client = SomeClient(...)`.
- Sync DB drivers (`psycopg2` for runtime paths, blocking `azure.cosmos.CosmosClient`). `psycopg2-binary` is acceptable for migration scripts only.
- `if/elif` over provider names anywhere outside a `Registry[T]`.
