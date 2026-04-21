# CWYD v2 — Modernization Plan

## 1. Overview

v1 has accumulated significant tech debt: a monolithic config singleton (150+ env vars), four parallel orchestration strategies with deprecated APIs, beta SDK dependencies, Key Vault for storing app config, and no native async support. v2 rewrites the backend on **FastAPI**, consolidates orchestration on **LangChain 0.3+ / LangGraph** with **Azure AI Agent Framework**, removes Key Vault secrets in favor of **RBAC + direct env vars** (following the MACAE pattern), uses **`uv`** as the package manager, and integrates the Admin UI directly into the React frontend.

---

## 2. Architecture: v1 → v2

```
v1 Architecture                          v2 Architecture
─────────────────                        ─────────────────
Flask (sync) ──────────────────────►     FastAPI (native async)
Streamlit Admin (separate service) ►     Admin integrated in React frontend
4 Orchestrators (OpenAI Fn, LC,    ►     LangGraph + Azure AI Agent Framework
  SK, Prompt Flow)
EnvHelper singleton (150+ vars) ───►     Pydantic Settings (typed, validated)
Key Vault for app secrets ─────────►     RBAC + env vars (no Key Vault secrets)
azure-search-documents 11.6.0b1 ──►     azure-search-documents (stable GA)
LangChain 0.2 (deprecated APIs) ──►     LangChain 0.3+ / LangGraph 0.4+
Manual streaming generators ──────►     FastAPI StreamingResponse + SSE
Factory pattern per subsystem ─────►     Dependency injection (FastAPI Depends)
Coupled auth logic everywhere ─────►     Middleware + dependency-injected auth
Poetry / pip (package manager) ────►     uv (fast, modern)
Cosmos DB only (MVP) ─────────────►     Cosmos DB OR PostgreSQL (selectable)
Separate infra (no DB choice) ────►     Clean Bicep with DB type parameter
```

---

## 3. Library Upgrades

### 3.1 Backend — Python

| Area | v1 (Current) | v2 (Target) | Rationale |
|---|---|---|---|
| **Runtime** | Python 3.10+ | **Python 3.12+** | Performance improvements, better typing, `ExceptionGroup` |
| **Package Manager** | Poetry / pip | **uv** | 10-100x faster installs, lockfile, replaces pip + virtualenv + poetry |
| **Web Framework** | Flask 3.1.2 | **FastAPI 0.115+** | Native async, Pydantic integration, OpenAPI auto-docs, dependency injection |
| **ASGI Server** | Werkzeug (dev) | **Uvicorn 0.34+** | Production-grade ASGI, already a v1 dependency |
| **Orchestration** | LangChain 0.2.17 + SK 1.39 + OpenAI Functions + Prompt Flow | **LangGraph 0.4+** + **Azure AI Agent Framework** | Graph-based orchestration + Microsoft's agent SDK for agentic patterns |
| **LLM Client** | openai 1.109, langchain-openai 0.1.25 | **openai 2.x+**, **langchain-openai 0.3+** | Current APIs, structured outputs, response_format |
| **Agent Framework** | N/A | **azure-ai-projects + azure-ai-agents** | Microsoft Agent Framework for agent lifecycle, tool management, tracing |
| **Configuration** | EnvHelper singleton | **pydantic-settings 2.x** | Typed config, .env loading, validation at startup, no god class |
| **Secrets/Auth** | Key Vault secrets + keys | **RBAC only (Managed Identity)** | No secrets to rotate, cleaner infra, follows MACAE pattern |
| **Search SDK** | azure-search-documents **11.6.0b1** | **azure-search-documents 11.6.x GA** | Stable release, no beta |
| **Cosmos DB** | azure-cosmos 4.14 | **azure-cosmos 4.14+** (keep) | Already current, add async client |
| **PostgreSQL** | psycopg2-binary + asyncpg | **asyncpg + pgvector** | Full async, vector search support |
| **Telemetry** | azure-monitor-opentelemetry 1.6 | **azure-monitor-opentelemetry 1.6+** (keep) | Already current |
| **Data Validation** | Manual / jsonschema | **Pydantic v2** | Request/response models, config validation, serialization |
| **Testing** | pytest + pytest-cov | **pytest + pytest-asyncio + httpx** | Async test support, `TestClient` for FastAPI |
| **Doc Intelligence** | azure-ai-formrecognizer 3.3.3 | **azure-ai-documentintelligence 1.x** | Renamed SDK, new API surface |

### 3.2 Frontend — TypeScript / React

| Area | v1 (Current) | v2 (Target) | Rationale |
|---|---|---|---|
| **React** | 19.2.4 | **19.x** (keep) | Already current |
| **Build** | Vite 7.3 | **Vite 7.x** (keep) | Already current |
| **UI Library** | Fluent UI v8 | **Fluent UI v9** (@fluentui/react-components) | v8 in maintenance mode, v9 is the active development path |
| **Admin UI** | Streamlit (separate service on :8501) | **React pages integrated in main frontend** | Single app, no separate service, shared auth |
| **State** | Props drilling / local state | **React Context + useReducer** (minimal) | Keep simple, avoid heavy state libs for MVP |
| **Streaming** | Custom JSON-lines parser | **EventSource / fetch ReadableStream** with typed events | Standard SSE protocol |
| **Testing** | Jest 30 + Testing Library | Keep (already modern) | — |

### 3.3 Libraries to Remove

| Library | Reason |
|---|---|
| `semantic-kernel` | Consolidating on LangGraph + Agent Framework |
| `promptflow[azure]` | Consolidating on LangGraph |
| `langchain` 0.2 + `langchain-community` 0.2 | Replaced by 0.3+ |
| `streamlit` | Admin UI moves into React frontend |
| `flask` | Replaced by FastAPI |
| `jsonschema` | Replaced by Pydantic |
| `poetry` | Replaced by `uv` |

---

## 4. Key Architectural Changes

### 4.1 No Key Vault for App Configuration

**v1 pattern** — Stores `FUNCTION-KEY` and other secrets in Key Vault, referenced at runtime:
```
App → Key Vault → Get Secret → Use value
```

**v2 pattern** (following [MACAE](https://github.com/microsoft/Multi-Agent-Custom-Automation-Engine-Solution-Accelerator)):
- **RBAC + Managed Identity** for all service-to-service auth
- **Environment variables** passed directly via Bicep → Container App / App Service config
- **No secrets array** — `secrets: []` on container definitions
- **Key Vault only for WAF compliance** (empty, deployed but unused for app config)
- Configuration flows: `Bicep outputs → azd → .env (local)` / `Bicep → Container env (deployed)`

Benefits:
- No secret rotation needed (RBAC tokens auto-rotate)
- No Key Vault latency on cold start
- Simpler infra (fewer dependencies)
- Easier local dev (just `.env` file)

### 4.2 Package Manager — uv

Replace Poetry + pip with `uv` across the project:

```toml
# pyproject.toml (v2)
[project]
name = "cwyd-v2"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn>=0.34",
    "langgraph>=0.4",
    "langchain-openai>=0.3",
    "azure-ai-projects>=1.0",
    "azure-cosmos>=4.14",
    "pydantic-settings>=2.0",
    # ...
]

[tool.uv]
dev-dependencies = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "httpx>=0.27",
]
```

Commands:
```bash
uv sync              # Install all deps (replaces poetry install)
uv run pytest        # Run tests (replaces poetry run pytest)
uv run uvicorn ...   # Run app
uv lock              # Generate/update lockfile
```

### 4.3 Clean Infrastructure (Cosmos DB or PostgreSQL)

v2 infra has a **single `databaseType` parameter** that switches the entire DB layer:

```bicep
@allowed(['cosmosdb', 'postgresql'])
@description('Database engine: CosmosDB (serverless NoSQL) or PostgreSQL (pgvector).')
param databaseType string = 'cosmosdb'

// Conditionally deploy one or the other
module cosmosDb '...' = if (databaseType == 'cosmosdb') { ... }
module postgresql '...' = if (databaseType == 'postgresql') { ... }

// App receives endpoint via env var regardless of choice
// AZURE_DATABASE_ENDPOINT = cosmosDb.outputs.endpoint ?? postgresql.outputs.fqdn
```

Infra structure:
```
v2/infra/
├── main.bicep              # Entry point with databaseType param
├── main.parameters.json    # Default params (cosmosdb)
├── modules/
│   ├── ai-services.bicep   # Azure OpenAI / Foundry IQ
│   ├── cosmosdb.bicep      # Cosmos DB (conditional)
│   ├── postgresql.bicep    # PostgreSQL Flexible Server (conditional)
│   ├── search.bicep        # Azure AI Search
│   ├── storage.bicep       # Blob Storage
│   ├── container-app.bicep # Backend hosting
│   ├── web-app.bicep       # Frontend hosting
│   ├── identity.bicep      # User-assigned managed identity + RBAC
│   └── monitoring.bicep    # Log Analytics + App Insights (optional)
└── scripts/
    └── post-deploy.sh      # Post-deployment setup
```

### 4.4 Azure AI Agent Framework Integration

v2 uses the [Microsoft Agent Framework](https://learn.microsoft.com/en-us/agent-framework/) alongside LangGraph:

- **LangGraph** handles the RAG orchestration graph (retrieve → generate flow)
- **Azure AI Agent Framework** (`azure-ai-projects` + `azure-ai-agents`) provides:
  - Agent lifecycle management (create, invoke, manage)
  - Built-in tool definitions (Azure AI Search grounding, code interpreter)
  - Tracing and observability via Foundry IQ
  - Multi-agent coordination (future)

```python
from azure.ai.projects import AIProjectClient
from azure.ai.agents import AgentsClient

# Agent Framework for agent management
project_client = AIProjectClient(
    endpoint=settings.ai_project_endpoint,
    credential=credential,
)

# LangGraph for RAG orchestration
from langgraph.graph import StateGraph
graph = StateGraph(ConversationState)
graph.add_node("retrieve", retrieve_documents)
graph.add_node("generate", generate_response)
```

### 4.5 Admin UI Integrated in Frontend

**v1**: Streamlit app on port 8501 (separate service, separate auth, separate deployment)

**v2**: Admin pages as React routes inside the main frontend:

```
/                  → Chat UI (default)
/admin             → Admin dashboard
/admin/upload      → Document upload & management
/admin/data        → Explore indexed data
/admin/config      → Configuration settings
/admin/index       → Search index management
```

Benefits:
- Single deployment (one frontend container)
- Shared authentication (no separate auth flow)
- Consistent UI (Fluent UI v9 throughout)
- Reduced infra (no Admin App Service)

---

## 5. Backend Architecture (Detail)

### 5.1 Project Layout

```
v2/src/backend/
├── main.py                     # FastAPI app entry point
├── dependencies.py             # Shared FastAPI dependencies (auth, config, db)
├── routers/
│   ├── conversation.py         # POST /api/conversation (chat + streaming)
│   ├── files.py                # GET /api/files/<filename>
│   ├── health.py               # GET /api/health
│   ├── speech.py               # GET /api/speech
│   ├── history.py              # /api/history/* CRUD
│   └── admin.py                # Admin API endpoints (upload, config, index)
├── models/
│   ├── requests.py             # Pydantic request models
│   ├── responses.py            # Pydantic response models
│   └── config.py               # Settings classes (pydantic-settings)
└── middleware/
    ├── auth.py                 # Authentication middleware
    └── error_handler.py        # Structured error responses
```

### 5.2 Shared Library

```
v2/src/shared/
├── config/
│   ├── settings.py             # Pydantic Settings (replaces EnvHelper)
│   └── assistant_config.py     # Assistant/prompt config (replaces active.json)
├── llm/
│   ├── client.py               # Azure OpenAI client factory (async)
│   └── embeddings.py           # Embedding client
├── orchestrator/
│   ├── graph.py                # LangGraph orchestration graph
│   ├── nodes.py                # Graph nodes (retrieve, generate, safety check)
│   ├── state.py                # Graph state definition
│   └── agent.py               # Azure AI Agent Framework integration
├── search/
│   ├── azure_search.py         # Azure AI Search handler (async)
│   └── postgres_search.py      # PostgreSQL + pgvector handler (async)
├── chat_history/
│   ├── base.py                 # Abstract base for chat history
│   ├── cosmosdb.py             # Cosmos DB chat history (async)
│   └── postgres.py             # PostgreSQL chat history (async)
├── parsers/
│   ├── document_loader.py      # Document loading (Layout, Read, Web)
│   └── chunking.py             # Document chunking strategies
├── tools/
│   ├── search_tool.py          # RAG search tool for LangGraph
│   ├── content_safety.py       # Content safety checker
│   └── post_prompt.py          # Post-answering validation
└── common/
    ├── credentials.py          # Azure credential factory (Managed Identity / CLI)
    ├── blob_storage.py         # Blob storage client (async)
    └── errors.py               # Custom exception hierarchy
```

### 5.3 Configuration — Pydantic Settings (No Key Vault)

```python
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal

class AzureSearchSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AZURE_SEARCH_")
    service: str
    index: str
    use_semantic_search: bool = True
    top_k: int = 5

class OpenAISettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AZURE_OPENAI_")
    endpoint: str                    # From Bicep output, not Key Vault
    model: str = "gpt-4.1"
    temperature: float = 0.0
    max_tokens: int = 1000

class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AZURE_DB_")
    type: Literal["cosmosdb", "postgresql"] = "cosmosdb"
    endpoint: str                    # Cosmos endpoint OR PostgreSQL FQDN
    name: str = "cwyd"

class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    search: AzureSearchSettings = AzureSearchSettings()
    openai: OpenAISettings = OpenAISettings()
    database: DatabaseSettings = DatabaseSettings()
    auth_type: Literal["rbac"] = "rbac"  # RBAC only, no keys
    # All auth is via Managed Identity — no secrets stored anywhere
```

### 5.4 Orchestration — LangGraph + Agent Framework

```
┌─────────┐    ┌──────────────┐    ┌──────────┐    ┌────────────────┐    ┌────────┐
│  Input   │───►│ Safety Check │───►│ Retrieve │───►│ Generate (LLM) │───►│ Output │
│ (user    │    │ (content     │    │ (search  │    │ (w/ citations) │    │ (stream│
│  message)│    │  safety API) │    │  tool)   │    │                │    │  SSE)  │
└─────────┘    └──────────────┘    └──────────┘    └────────────────┘    └────────┘
                     │ block                              │
                     ▼                              ┌─────▼──────┐
                ┌─────────┐                         │ Post-Prompt│
                │ Blocked │                         │ Validation │
                │ Response│                         └────────────┘
                └─────────┘
```

**LangGraph** = the orchestration engine (graph definition, state management, streaming)
**Agent Framework** = Azure-native agent lifecycle (tool registration, tracing, Foundry IQ integration)

---

## 6. Migration Strategy

> **Principle**: Every phase ends with a working `azd up`. Each phase delivers a vertical slice: infra + data + backend + frontend — even if minimal.

### Phase 1: Infrastructure + Project Skeleton
> `azd up` → all Azure resources deployed, stub apps running, sample data loaded

- Clean Bicep infra with `databaseType` parameter (Cosmos DB or PostgreSQL)
- User-assigned managed identity + RBAC roles (no Key Vault secrets)
- Foundry IQ resource (knowledge base, embeddings, model deployments)
- `azure.yaml` with v2 service paths
- Stub FastAPI backend (`/api/health` returns 200)
- Stub React frontend (placeholder page)
- Dockerfiles for backend + frontend
- Post-deploy script loads sample data to Blob Storage

### Phase 2: Configuration + LLM Integration
> `azd up` → configured backend, chat UI shell, all Azure connections validated

- Pydantic Settings replacing EnvHelper (no Key Vault)
- Foundry IQ client (knowledge base, embeddings)
- Azure credential factory (Managed Identity deployed, Azure CLI local)
- Health check with dependency validation
- Frontend: basic chat UI shell
- `uv` project fully configured

### Phase 3: Conversation + RAG (Core Chat)
> `azd up` → working chat with streamed answers and citations from sample docs

- LangGraph orchestrator (safety → retrieve → generate)
- Azure AI Agent Framework integration
- Azure AI Search handler (async)
- SSE streaming via `POST /api/conversation`
- Citation extraction and formatting
- Frontend chat connected to backend
- Scripts: create search index + index sample documents

### Phase 4: Chat History + Both Databases
> `azd up` → persistent chat on either Cosmos DB or PostgreSQL

- Cosmos DB async chat history (CRUD)
- PostgreSQL async chat history (CRUD)
- Database factory (selects via `DATABASE_TYPE` env var)
- PostgreSQL + pgvector search handler
- History API + frontend history panel

### Phase 5: Admin + Frontend Merge
> `azd up` → full frontend with admin pages, auth, document management

- Admin API endpoints (upload, config, status)
- React admin pages integrated in frontend
- Files, speech, auth routers
- Remove all Streamlit references

### Phase 6: RAG Indexing Pipeline
> `azd up` → end-to-end: upload document → functions process → index → chat

- Split Azure Functions (batch_start, batch_push, add_url, search_skill)
- Embedder factory + implementations
- LangChain PostgreSQL vector indexing
- Integrated vectorization

### Phase 7: Testing + Documentation
> `azd up` → production-ready, fully tested and documented

- Comprehensive pytest + Jest test suites
- Migration guide and updated docs
- Final cleanup (remove all v1 orchestrator references)

---

## 7. Configuration & Customization

### 7.1 Configuration Layers

| Layer | When Set | What It Controls | Example |
|---|---|---|---|
| **Bicep Parameters** | Deploy time (`azd up`) | Azure resource choices | `databaseType`, `gptModelName`, `enableMonitoring` |
| **Environment Variables** | Deploy time (from Bicep outputs) | Service endpoints, connection info | `AZURE_OPENAI_ENDPOINT`, `AZURE_DB_ENDPOINT` |
| **Pydantic Settings** | Runtime (loaded from env) | Typed, validated app config | `AppSettings.search.top_k`, `AppSettings.openai.temperature` |
| **active.json** | Runtime (hot-reloadable) | Prompts, orchestrator, UI behavior | System prompt, document processors, UI branding |

### 7.2 Customization Points

| What to Customize | How | File(s) |
|---|---|---|
| **Database backend** | Set `databaseType` Bicep param | `main.parameters.json` |
| **Chat model** | Set `AZURE_OPENAI_MODEL` env var | `.env` / Bicep |
| **Embedding model** | Set `AZURE_OPENAI_EMBEDDING_MODEL` env var | `.env` / Bicep |
| **System prompt** | Edit `active.json` → `prompts.system_message` | `data/active.json` |
| **Orchestrator** | Set `ORCHESTRATOR` env var or `active.json` | `.env` / `active.json` |
| **Search behavior** | Modify search settings via env vars | `.env` |
| **Document processing** | Edit `active.json` → `document_processors` | `data/active.json` |
| **UI branding** | Edit `active.json` → `ui` section | `data/active.json` |
| **Add a new tool** | Implement in `shared/tools/`, register in orchestrator | `shared/tools/` |
| **WAF-aligned deploy** | Enable monitoring, scalability, redundancy, private networking params | `main.parameters.json` |

### 7.3 Local Dev Config

All config comes from `.env` (generated by `azd env get-values` or created manually):
```bash
AZURE_OPENAI_ENDPOINT=https://your-ai-services.openai.azure.com/
AZURE_OPENAI_MODEL=gpt-4.1
AZURE_SEARCH_SERVICE=your-search-service
AZURE_DB_TYPE=cosmosdb
AZURE_DB_ENDPOINT=https://your-cosmos.documents.azure.com:443/
```

---

## 8. Key Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| **Infra first** | Phase 1 is infrastructure | Every phase is `azd up` deployable; early validation of Azure resources |
| Single orchestrator | LangGraph + Agent Framework | Eliminates 4 parallel code paths; graph model + Azure-native agent lifecycle |
| Drop Semantic Kernel | Yes | LangGraph + Agent Framework covers the same patterns |
| Drop Prompt Flow | Yes | LangGraph provides flow orchestration natively |
| FastAPI over Flask | FastAPI | Native async, Pydantic integration, auto-generated OpenAPI docs |
| `uv` over Poetry/pip | `uv` | 10-100x faster, single tool for venv + install + lock + run |
| No Key Vault secrets | Yes | RBAC + Managed Identity, following MACAE pattern |
| Pydantic Settings | Yes | Type-safe config, validation at startup, composable |
| Both DBs in MVP | Yes | Cosmos DB and PostgreSQL both supported from day one |
| Admin in frontend | Yes | Single deployment, shared auth, consistent UI |
| Async everywhere | Yes | FastAPI + async Azure SDKs enable high-throughput I/O |
| Clean Bicep + DB param | Yes | One `databaseType` parameter switches all DB infra |
| Agent Framework | Yes | Microsoft's native SDK for agent management + Foundry IQ integration |
| Foundry IQ | Knowledge base, embeddings | Centralized model + knowledge management; clean separation from orchestration |
