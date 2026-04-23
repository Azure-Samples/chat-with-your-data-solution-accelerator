---
description: "CWYD v2 shared layer conventions (orchestrators, LLM helper, tools, search, embedders, chat history). Use when: editing v2/src/shared/**, building an orchestrator, adding a tool, calling Foundry IQ, adding a search handler, adding an embedder, adding a chat history backend, defining the OrchestratorEvent contract, or wiring async credentials."
applyTo: "v2/src/shared/**"
---

# v2 Shared Layer Conventions

## Stack rules

- **Foundry IQ only** for model + knowledge access. No `from openai import AzureOpenAI`.
- LangGraph for graph-based orchestration. No `langchain.agents.ZeroShotAgent` / `AgentExecutor` (legacy).
- Azure AI Agent Framework (`azure-ai-agents`) for managed-agent orchestration.
- All I/O is async. All clients are constructed via factories — no module-level instantiation.

## Orchestrator contract

`shared/orchestrator/base.py` defines:

```python
class OrchestratorBase(ABC):
    @abstractmethod
    async def run(self, request: ConversationRequest) -> AsyncIterator[OrchestratorEvent]: ...
```

Every concrete orchestrator (`openai_functions.py`, `langgraph_agent.py`, `azure_agents.py`):

1. Inherits `OrchestratorBase`.
2. Emits events on channels: `reasoning`, `tool`, `answer`, `citation`, `error`. Never inline reasoning into `answer`.
3. Pre-pipeline: content safety check on input. Post-pipeline: post-prompt formatting + content safety check on output. Both live in `shared/tools/`.
4. Registers itself in `shared/orchestrator/orchestrator.py` factory by name (`"openai_functions" | "langgraph" | "agent_framework"`).

## Foundry IQ client

- Single class `FoundryIQClient` in `shared/llm/llm_helper.py`.
- Methods: `chat(...)`, `chat_stream(...)`, `embed(...)`, `reason(...)` (o-series; routes to a reasoning deployment).
- Constructor takes `AppSettings` and a `TokenCredential`. Never reads env vars directly.
- `reason()` yields `OrchestratorEvent(channel="reasoning", ...)` and `OrchestratorEvent(channel="answer", ...)` separately.

## Credentials

- `shared/common/credentials.py::get_credential()` returns `DefaultAzureCredential` deployed, `AzureCliCredential` locally.
- Selected by `AZURE_CLIENT_ID` presence (deployed Managed Identity has it set).
- Async: prefer `azure.identity.aio.DefaultAzureCredential` for use in async clients.

## Tool registration

- Each tool in `shared/tools/<name>.py` exports a `Tool` instance with `name`, `description`, `args_schema` (Pydantic), `arun(...)` async method.
- Tools are pillar-tagged in their docstring. Most are **Stable Core**; scenario-specific ones are **Scenario Pack**.

## Search handlers

- Both `azure_search_helper.py` and `postgres_handler.py` implement `SearchHandlerBase` with `async def search(query, top_k, filters) -> list[SearchResult]`.
- `SearchResult` is a Pydantic model with `id`, `content`, `score`, `metadata`.

## Chat history

- `database_factory.py::get_chat_history()` returns the configured backend. Picks via `AppSettings.database.type`.
- Both backends implement `ChatHistoryBase` (CRUD + feedback). Async only.

## Banned

- `from openai import …` anywhere in `v2/src/shared/**`.
- `semantic_kernel`, `promptflow`.
- Module-level `client = SomeClient(...)`.
- Sync DB drivers (`psycopg2`, blocking `azure.cosmos.CosmosClient`).
