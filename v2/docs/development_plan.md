# CWYD v2 — Development Plan Proposal

**Repo**: [Azure-Samples/chat-with-your-data-solution-accelerator](https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator)
**Branch**: `dev-v2`
**Date**: April 2026

---

## Summary

Modernize the Chat With Your Data Solution Accelerator from a monolithic Flask application with four co-installed orchestrators into a modular **FastAPI + Azure Functions** architecture. Replace the direct Azure OpenAI SDK with **Foundry IQ** (Knowledge Base, Embeddings), remove Prompt Flow, Semantic Kernel, Streamlit admin, one-click deploy, and Poetry references, add the **Azure AI Agent Framework** with reasoning model support, upgrade **LangChain to LangGraph** for PostgreSQL indexing, and split **Azure Functions** into a modular RAG indexing pipeline. Azure Bot Service and Teams plugin are deferred to a future version.

**Key principle**: Infrastructure is Phase 1. Every phase results in a deployable `azd up` solution — some infra, some data, some scripts, some backend, and some frontend — even if they don't look great yet.

---

## 1. Current State (v1)

### 1.1 Technology Stack

| Layer | Technology |
|-------|-----------|
| Backend | Flask + Uvicorn, monolithic `code/` directory |
| Admin | Streamlit (`code/backend/Admin.py`) — separate Python web app |
| Frontend | React 19, TypeScript, Vite, Fluent UI |
| Functions | Azure Functions (Python 3.11) — batch document processing |
| Model Access | Direct Azure OpenAI SDK (GPT-\*, text-embedding-3-small) |
| Databases | Azure Cosmos DB **or** PostgreSQL Flexible Server (switchable at deploy time) |
| Configuration | Monolithic `EnvHelper` singleton — 100+ environment variables |
| Infrastructure | Bicep IaC, Azure Developer CLI (`azd`), one-click "Deploy to Azure" ARM button |
| Package Managers | `uv` (Python), `npm` (Node) |

### 1.2 Orchestration Strategies (4, runtime-switchable)

| Strategy | Implementation |
|----------|---------------|
| **OpenAI Functions** | Direct Azure OpenAI function/tool calling |
| **Semantic Kernel** | Microsoft SK framework with plugins |
| **LangChain** | `ZeroShotAgent` + `AgentExecutor` (legacy pattern) |
| **Prompt Flow** | Azure ML deployed endpoint invocation |

### 1.3 Azure Services

- Azure OpenAI (GPT-\*, embeddings) — direct SDK calls
- Azure AI Search (vector + semantic search)
- Azure Storage (Blob + Queue)
- Azure Cosmos DB / PostgreSQL Flexible Server (pgvector)
- Azure Key Vault, Document Intelligence, Content Safety, Speech Services
- Azure App Service (frontend + admin), Azure Functions
- Application Insights, Log Analytics, Event Grid
- Optional: Computer Vision, VNet + Private Endpoints, Bastion

### 1.4 Deployment

- One-click "Deploy to Azure" button (ARM template)
- Azure Developer CLI (`azd up`)
- Docker Compose (local development)
- Supported regions: australiaeast, eastus2, japaneast, uksouth

### 1.5 Architecture Diagram (v1)

```
┌─────────────────────────────────────────────────────────┐
│                       USERS                             │
└────────────────────────┬────────────────────────────────┘
                         │
          ┌──────────────▼──────────────┐
          │   React/Vite Frontend       │
          │   Azure App Service         │
          └──────────────┬──────────────┘
                         │
          ┌──────────────▼──────────────┐
          │   Flask Backend (Uvicorn)   │
          │   code/create_app.py        │
          │   Azure App Service         │
          └──┬───────────┬──────────┬───┘
             │           │          │
    ┌────────▼───┐  ┌────▼────┐  ┌─▼──────────────────┐
    │ Orchestrator│  │Chat     │  │ Azure OpenAI       │
    │ (4 options) │  │History  │  │ (Direct SDK)       │
    │ SK / LC /   │  │CosmosDB │  │ GPT-* + Embeddings │
    │ PF / OAI    │  │or PG    │  └────────────────────┘
    └──────┬──────┘  └─────────┘
           │
    ┌──────▼─────────────┐    ┌───────────────────────┐
    │ Shared Tools        │    │ Streamlit Admin       │
    │ QA, TextProc,       │    │ code/backend/Admin.py │
    │ ContentSafety       │    │ Azure App Service     │
    └──────┬──────────────┘    └───────────────────────┘
           │
    ┌──────▼─────────────┐
    │ Search Handlers     │
    │ AI Search / PG      │
    └─────────────────────┘

    ┌─────────────────────────────────────────┐
    │  Azure Functions (Monolithic)            │
    │  Batch processing — blob → queue → index │
    └─────────────────────────────────────────┘
```

---

## 2. What Changes in v2

### 2.1 Removals

| Component | Reason |
|-----------|--------|
| **One-click "Deploy to Azure" button** | Simplify to `azd`-only; ARM template maintenance overhead |
| **Poetry references** | Fully standardized on `uv`; remove any lingering Poetry config |
| **Prompt Flow orchestrator** | Replaced by Agent Framework; drops Azure ML dependency |
| **Semantic Kernel orchestrator** | Consolidate to fewer, more strategic orchestrators |
| **Streamlit admin app** | Admin features merged into the React/Vite frontend |
| **Direct Azure OpenAI SDK** | Replaced by Foundry IQ for knowledge base and embeddings |
| **Azure Bot Service / Teams extension** | Deferred to a future version |
| **Key Vault for app secrets** | Replaced by RBAC + direct env vars (MACAE pattern) |

### 2.2 Additions

| Component | Purpose |
|-----------|---------|
| **Azure AI Agent Framework** | Modern agent orchestration — replaces Semantic Kernel and Prompt Flow |
| **Foundry IQ** (Knowledge Base, Embeddings) | Centralized knowledge base, embeddings, and model access (GPT-\*, o-series reasoning) |

### 2.3 Updates

| Component | From → To |
|-----------|-----------|
| **Web framework** | Flask → **FastAPI** (async-native, OpenAPI docs, dependency injection) |
| **LangChain orchestrator** | `ZeroShotAgent` / `AgentExecutor` → **LangGraph** (`StateGraph` + `ToolNode`) |
| **Azure Functions** | Monolithic → **split into modular RAG indexing pipeline** |
| **Configuration** | `EnvHelper` singleton → **Pydantic `BaseSettings`** (typed, validated, nested) |
| **Project structure** | Monolithic `code/` → **modular `v2/src/`** (backend, frontend, functions, shared) |
| **Admin UI** | Standalone Streamlit app → **merged into React/Vite frontend** |
| **Bicep infrastructure** | Updated to add Foundry IQ resources, remove Azure ML references, remove one-click ARM |

---

## 3. v2 Target Architecture

### 3.1 High-Level Architecture

```
                    ┌──────────────────────────────────┐
                    │           USERS (Browser)         │
                    └───────────────┬──────────────────┘
                                    │
                    ┌───────────────▼──────────────────┐
                    │   React/Vite Frontend             │
                    │   (Chat + Admin — unified)        │
                    │   Azure App Service               │
                    └───────────────┬──────────────────┘
                                    │ REST API
                    ┌───────────────▼──────────────────┐
                    │   FastAPI Backend                  │
                    │   Routers: conversation, admin,    │
                    │   chat_history, files, speech,     │
                    │   auth, health                     │
                    │   Azure App Service                │
                    └──┬────────────┬───────────────┬──┘
                       │            │               │
              ┌────────▼───┐  ┌─────▼──────┐  ┌────▼──────────────┐
              │ Orchestrator│  │ Chat       │  │  Foundry IQ       │
              │ Router      │  │ History    │  │  (Knowledge Base, │
              │             │  │ CosmosDB   │  │   Embeddings)     │
              │ ┌─────────┐ │  │ or         │  │  ├─ GPT-*        │
              │ │LangGraph│ │  │ PostgreSQL │  │  ├─ o-series     │
              │ └─────────┘ │  └────────────┘  │  │  (reasoning)  │
              │ ┌─────────┐ │                  │  └─ Embeddings  │
              │ │Agent    │ │                  └──────────────────┘
              │ │Framework│ │
              │ └─────────┘ │
              │ ┌─────────┐ │
              │ │OpenAI   │ │
              │ │Functions │ │
              │ └─────────┘ │
              └──────┬──────┘
                     │
              ┌──────▼──────────────────────┐
              │  Shared Tools Layer           │
              │  Question & Answer            │
              │  Text Processing              │
              │  Content Safety               │
              │  Post-Prompt Formatting       │
              └──────┬──────────────────────┘
                     │
              ┌──────▼──────────────────────┐
              │  Search Handlers              │
              │  Azure AI Search              │
              │  PostgreSQL (pgvector)         │
              │  Integrated Vectorization      │
              └──────────────────────────────┘
```

### 3.2 RAG Indexing Pipeline (Split Azure Functions)

```
 ┌──────────────┐     ┌──────────────┐     ┌──────────────────┐
 │ Blob Storage  │────▶│ Event Grid   │────▶│ Queue Storage    │
 │ (Documents)   │     │ (Trigger)    │     │ (Processing Msgs)│
 └──────────────┘     └──────────────┘     └────────┬─────────┘
                                                     │
                      ┌──────────────────────────────▼──────────┐
                      │      Azure Functions (Split / Modular)   │
                      │                                          │
                      │  ┌──────────────────┐                    │
                      │  │ batch_start      │ List blobs,        │
                      │  │                  │ queue messages      │
                      │  └────────┬─────────┘                    │
                      │           │                              │
                      │  ┌────────▼─────────┐                    │
                      │  │ batch_push       │ Parse, chunk,      │
                      │  │                  │ embed, push to     │
                      │  │                  │ search index        │
                      │  └────────┬─────────┘                    │
                      │           │                              │
                      │  ┌────────▼─────────┐                    │
                      │  │ add_url          │ Fetch URL content, │
                      │  │                  │ parse, embed        │
                      │  └──────────────────┘                    │
                      │                                          │
                      │  ┌──────────────────┐                    │
                      │  │ search_skill     │ Custom AI Search   │
                      │  │                  │ skill endpoint     │
                      │  └──────────────────┘                    │
                      └──────────────────────────────────────────┘
                                     │
                      ┌──────────────▼──────────────────┐
                      │  LangChain (PostgreSQL indexing)  │
                      │  pgvector embeddings              │
                      │  Azure AI Search indexing          │
                      └───────────────────────────────────┘
```

### 3.3 Orchestrator Migration (v1 → v2)

```
v1 Orchestrators                   v2 Orchestrators
─────────────────────              ─────────────────────────
OpenAI Functions      ──────────▶  OpenAI Functions (kept, via Foundry)
Semantic Kernel       ─────╳────▶  REMOVED
LangChain Agent       ──────────▶  LangGraph Agent (upgraded)
Prompt Flow           ─────╳────▶  REMOVED
                                   Agent Framework (NEW)

Model Access:
v1: Direct Azure OpenAI SDK  ──▶  v2: Foundry IQ
                                       (Knowledge Base, Embeddings)
                                       ├── GPT-*
                                       ├── o-series (reasoning)
                                       └── Embeddings
```

### 3.4 Project Structure (v2)

```
v2/
├── src/
│   ├── backend/                  # FastAPI application
│   │   ├── app.py                # App factory, lifespan, CORS, OpenTelemetry
│   │   ├── dependencies.py       # Dependency injection (settings, LLM helper)
│   │   ├── routers/
│   │   │   ├── conversation.py   # Chat endpoint (streaming + non-streaming)
│   │   │   ├── admin.py          # Admin API (config, SAS tokens, orchestrator)
│   │   │   ├── chat_history.py   # CRUD, feedback, status
│   │   │   ├── files.py          # Blob serving
│   │   │   ├── speech.py         # Azure Speech token
│   │   │   ├── auth.py           # Authentication
│   │   │   └── health.py         # Health check
│   │   └── models/               # Pydantic request/response models
│   │
│   ├── frontend/                 # React + Vite (Chat + Admin merged)
│   │   ├── src/
│   │   │   ├── pages/
│   │   │   │   ├── chat/         # Chat interface
│   │   │   │   └── admin/        # Admin pages (ingestion, config, explore)
│   │   │   ├── stores/           # Zustand state management
│   │   │   └── api/              # API client layer
│   │   └── ...
│   │
│   ├── functions/                # Azure Functions (split)
│   │   ├── function_app.py       # Function registration
│   │   └── blueprints/
│   │       ├── batch_start.py    # List blobs, queue messages
│   │       ├── batch_push.py     # Parse, chunk, embed, index
│   │       ├── add_url.py        # URL fetch + embed
│   │       └── search_skill.py   # Custom AI Search skill
│   │
│   └── shared/                   # Shared logic across backend + functions
│       ├── config/
│       │   ├── env_settings.py   # Pydantic BaseSettings (typed, nested)
│       │   ├── config_helper.py  # active.json loader
│       │   └── models.py         # Config schema
│       ├── orchestrator/
│       │   ├── orchestrator.py   # Strategy router / factory
│       │   ├── base.py           # Abstract base (safety pipeline)
│       │   ├── openai_functions.py
│       │   ├── langgraph_agent.py
│       │   └── azure_agents.py
│       ├── llm/
│       │   └── llm_helper.py     # Foundry IQ client (knowledge base, embeddings)
│       ├── tools/
│       │   ├── question_answer.py
│       │   ├── text_processing.py
│       │   ├── content_safety.py
│       │   └── post_prompt.py
│       ├── search/
│       │   ├── azure_search_helper.py
│       │   └── postgres_handler.py
│       ├── chat_history/
│       │   ├── database_factory.py
│       │   ├── cosmosdb.py
│       │   └── postgres.py
│       └── embedders/
│           ├── embedder_factory.py
│           ├── push_embedder.py
│           ├── postgres_embedder.py
│           └── integrated_vectorization.py
│
├── infra/                        # Bicep infrastructure
│   ├── main.bicep                # Entry point with databaseType param
│   ├── main.parameters.json
│   └── modules/
│       ├── ai-services.bicep     # Foundry IQ + OpenAI deployments
│       ├── cosmosdb.bicep        # Cosmos DB (conditional)
│       ├── postgresql.bicep      # PostgreSQL Flexible Server (conditional)
│       ├── search.bicep          # Azure AI Search
│       ├── storage.bicep         # Blob Storage
│       ├── container-app.bicep   # Backend hosting
│       ├── web-app.bicep         # Frontend hosting
│       ├── identity.bicep        # User-assigned managed identity + RBAC
│       └── monitoring.bicep      # Log Analytics + App Insights (optional)
│
├── data/
│   └── sample/                   # Sample documents for bootstrap
│
├── scripts/
│   └── post-deploy.sh            # Post-deployment data loading + index creation
│
├── azure.yaml                    # azd service definitions
├── pyproject.toml                # uv project config
└── Dockerfile                    # Backend container
```

---

## 4. Implementation Phases

> **Principle**: Every phase ends with a working `azd up`. Each phase delivers a vertical slice: infra + data + backend + frontend — even if minimal. This ensures continuous deployability and early validation.

### Phase 1 — Infrastructure + Project Skeleton

**Goal**: `azd up` deploys all Azure resources and stub applications. A browser can hit the frontend and see a placeholder page; the backend responds to `/api/health`.

| # | Task | Key Files |
|---|------|-----------|
| 1 | Clean Bicep infra with `databaseType` parameter (Cosmos DB or PostgreSQL) | `infra/main.bicep`, `infra/modules/` |
| 2 | User-assigned managed identity + RBAC roles (no Key Vault secrets) | `infra/modules/identity.bicep` |
| 3 | Foundry IQ resource (knowledge base, embeddings, model deployments) | `infra/modules/ai-services.bicep` |
| 4 | `azure.yaml` with v2 service paths (backend, frontend, functions) | `azure.yaml` |
| 5 | Stub FastAPI backend — `GET /api/health` returns 200 | `backend/app.py`, `backend/routers/health.py` |
| 6 | Stub React frontend — placeholder page with "CWYD v2" | `frontend/src/` |
| 7 | Dockerfiles for backend + frontend | `docker/` |
| 8 | Post-deploy script — loads sample data to Blob Storage | `scripts/post-deploy.sh` |
| 9 | Sample documents in `data/sample/` for bootstrap | `data/sample/` |

**`azd up` result**: All infra provisioned, stub apps running in Azure, sample data loaded, health check passes.

### Phase 2 — Configuration + LLM Integration

**Goal**: Backend has a real configuration system, connects to Foundry IQ, and health check validates all dependencies. Frontend shows a basic chat shell (no backend integration yet).

| # | Task | Key Files |
|---|------|-----------|
| 10 | Pydantic `BaseSettings` replacing `EnvHelper` (nested models per Azure service) | `shared/config/env_settings.py` |
| 11 | Foundry IQ client — knowledge base access + embeddings | `shared/llm/llm_helper.py` |
| 12 | Azure credential factory (Managed Identity deployed, Azure CLI local) | `shared/common/credentials.py` |
| 13 | Health router with dependency checks (DB, search, Foundry IQ connectivity) | `backend/routers/health.py` |
| 14 | Dependency injection wiring (settings → routers) | `backend/dependencies.py` |
| 15 | Frontend: basic chat UI shell (input box, message list, layout) | `frontend/src/pages/chat/` |
| 16 | Bicep outputs wired to backend env vars (no Key Vault) | `infra/main.bicep` |

**`azd up` result**: Configured backend with detailed health check, frontend shell visible, all Azure service connections validated.

### Phase 3 — Conversation + RAG (Core Chat)

**Goal**: A user can type a message and get a streamed answer grounded in indexed documents. This is the first "it works!" moment.

| # | Task | Key Files |
|---|------|-----------|
| 17 | Orchestrator router / factory (strategy pattern dispatch) | `shared/orchestrator/orchestrator.py` |
| 18 | OpenAI Functions orchestrator (tool calling via Foundry IQ) | `shared/orchestrator/openai_functions.py` |
| 19 | LangGraph agent — `StateGraph` + `ToolNode` | `shared/orchestrator/langgraph_agent.py` |
| 20 | Shared tools layer (QA, text processing, content safety, post-prompt) | `shared/tools/*` |
| 21 | Azure AI Search handler (async) | `shared/search/azure_search_helper.py` |
| 22 | Conversation router (streaming SSE + non-streaming, BYOD + custom) | `backend/routers/conversation.py` |
| 23 | Citation extraction and formatting | `shared/tools/question_answer.py` |
| 24 | Frontend: chat connected to `/api/conversation`, SSE stream consumption | `frontend/src/pages/chat/` |
| 25 | Reasoning model support via Foundry IQ (o-series routing) | `shared/llm/llm_helper.py` |
| 26 | Scripts: create search index + index sample documents | `scripts/post-deploy.sh` |

**`azd up` result**: Working chat experience — user asks a question, gets a streamed answer with citations from sample documents.

### Phase 4 — Chat History + Both Databases

**Goal**: Conversations persist across sessions. Both Cosmos DB and PostgreSQL work as chat history backends. pgvector search enabled for PostgreSQL deployments.

| # | Task | Key Files |
|---|------|-----------|
| 27 | Chat history — Cosmos DB async client | `shared/chat_history/cosmosdb.py` |
| 28 | Chat history — PostgreSQL async client | `shared/chat_history/postgres.py` |
| 29 | Database factory (selects Cosmos DB or PostgreSQL based on `DATABASE_TYPE`) | `shared/chat_history/database_factory.py` |
| 30 | PostgreSQL + pgvector search handler (async) | `shared/search/postgres_handler.py` |
| 31 | Chat history router (CRUD, feedback, status) | `backend/routers/chat_history.py` |
| 32 | Frontend: conversation history panel (list, select, rename, delete) | `frontend/src/pages/chat/` |
| 33 | Azure AI Agent Framework orchestrator | `shared/orchestrator/azure_agents.py` |
| 34 | Bicep: ensure both DB conditional modules output correct env vars | `infra/modules/cosmosdb.bicep`, `postgresql.bicep` |

**`azd up` result**: Chat with persistent history — user returns later and sees previous conversations. Works with either database type.

### Phase 5 — Admin + Frontend Merge

**Goal**: Unified frontend with admin capabilities. Document management, system status, configuration view — all inside the React app.

| # | Task | Key Files |
|---|------|-----------|
| 35 | Admin API router (settings, config, SAS tokens, orchestrator switching) | `backend/routers/admin.py` |
| 36 | Admin pages in React frontend (data ingestion, config, exploration) | `frontend/src/pages/admin/` |
| 37 | Files router (blob serving) | `backend/routers/files.py` |
| 38 | Speech router (Azure Speech token) | `backend/routers/speech.py` |
| 39 | Auth router + middleware (RBAC, role-based admin access) | `backend/routers/auth.py` |
| 40 | Remove all Streamlit references | project-wide |

**`azd up` result**: Full frontend with chat + admin pages. Users can upload documents, view system config, check index status — all in one app.

### Phase 6 — RAG Indexing Pipeline (Split Functions)

**Goal**: Modular Azure Functions process uploaded documents end-to-end: blob → parse → chunk → embed → index. Completes the full ingestion loop.

| # | Task | Key Files |
|---|------|-----------|
| 41 | `batch_start` — list blobs, queue messages | `functions/blueprints/batch_start.py` |
| 42 | `batch_push` — parse, chunk, embed, push to search index | `functions/blueprints/batch_push.py` |
| 43 | `add_url` — URL fetch, parse, embed | `functions/blueprints/add_url.py` |
| 44 | `search_skill` — custom AI Search skill endpoint | `functions/blueprints/search_skill.py` |
| 45 | LangChain PostgreSQL vector indexing integration | `shared/search/postgres_handler.py` |
| 46 | Embedder factory + implementations (push, postgres, integrated vectorization) | `shared/embedders/*` |
| 47 | Bicep: Functions app + storage queues + event grid trigger | `infra/modules/` |

**`azd up` result**: End-to-end pipeline — upload a document via admin UI → functions process it → document appears in search → user can chat about it.

### Phase 7 — Testing + Documentation

**Goal**: Comprehensive test coverage, migration guide, and updated documentation.

| # | Task | Key Files |
|---|------|-----------|
| 48 | Port / rewrite pytest tests for FastAPI (`TestClient`), cover all 3 orchestrators | `tests/` |
| 49 | Update frontend Jest tests for admin features | `frontend/` |
| 50 | Update README with new architecture and setup instructions | `README.md` |
| 51 | Write v2 migration guide | `v2/docs/` |
| 52 | Update docs for new configuration, deployment, and orchestrator options | `docs/` |
| 53 | Remove all references to Prompt Flow, Semantic Kernel, Streamlit, Poetry, direct Azure OpenAI SDK | project-wide |

**`azd up` result**: Production-ready deployment — fully tested, documented, and clean.

---

## 5. Phase Dependency Graph

```
Phase 1 (Infra + Skeleton)          ← azd up: stub apps + all Azure resources
  │
  ▼
Phase 2 (Config + LLM)              ← azd up: configured backend, chat UI shell
  │
  ▼
Phase 3 (Conversation + RAG)        ← azd up: working chat with streaming + citations
  │
  ├──────────┐
  │          │
  ▼          ▼
Phase 4    Phase 5
(History    (Admin +
 + DBs)     Frontend)
  │          │
  └────┬─────┘
       ▼
Phase 6 (RAG Indexing Pipeline)      ← azd up: full ingestion + chat pipeline
       │
       ▼
Phase 7 (Testing + Docs)            ← azd up: production-ready
```

---

## 6. Configuration & Customization

### 6.1 Configuration Architecture

v2 uses a layered configuration system with **no Key Vault secrets**:

```
┌─────────────────────────────────────────────────────┐
│  Layer 1: Bicep Parameters                           │
│  (deploy-time choices: databaseType, region, SKU)    │
├─────────────────────────────────────────────────────┤
│  Layer 2: Bicep Outputs → Environment Variables      │
│  (service endpoints, resource names, connection info) │
├─────────────────────────────────────────────────────┤
│  Layer 3: Pydantic Settings (runtime config)         │
│  (typed, validated, composable, loaded from env)     │
├─────────────────────────────────────────────────────┤
│  Layer 4: active.json (assistant/prompt config)      │
│  (system prompts, orchestrator choice, UI behavior)  │
└─────────────────────────────────────────────────────┘
```

### 6.2 Deploy-Time Configuration (Bicep Parameters)

These are set once at `azd up` time and determine what Azure resources are provisioned:

| Parameter | Options | Default | Description |
|-----------|---------|---------|-------------|
| `databaseType` | `cosmosdb`, `postgresql` | `cosmosdb` | Which database engine to deploy |
| `location` | Azure regions | — | Primary deployment region |
| `azureAiServiceLocation` | AI-supported regions | — | Region for AI model deployments |
| `enableMonitoring` | `true`, `false` | `false` | Deploy Log Analytics + App Insights |
| `enableScalability` | `true`, `false` | `false` | Higher SKUs, autoscaling rules |
| `enableRedundancy` | `true`, `false` | `false` | Multi-region, zone-redundant |
| `enablePrivateNetworking` | `true`, `false` | `false` | VNet, private endpoints, bastion |
| `gptModelName` | Model names | `gpt-4.1` | Primary chat model |
| `embeddingModelName` | Model names | `text-embedding-3-small` | Embedding model |

### 6.3 Runtime Configuration (Environment Variables → Pydantic Settings)

These are set via Bicep outputs (deployed) or `.env` file (local dev):

```python
# Grouped by service — each group is a nested Pydantic model
class AzureOpenAISettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AZURE_OPENAI_")
    endpoint: str                    # From Bicep output
    model: str = "gpt-4.1"
    embedding_model: str = "text-embedding-3-small"
    temperature: float = 0.0
    max_tokens: int = 1000
    api_version: str = "2024-12-01-preview"

class AzureSearchSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AZURE_SEARCH_")
    service: str                     # From Bicep output
    index: str = "cwyd-index"
    use_semantic_search: bool = True
    semantic_search_config: str = "my-semantic-config"
    top_k: int = 5

class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AZURE_DB_")
    type: Literal["cosmosdb", "postgresql"] = "cosmosdb"
    endpoint: str                    # From Bicep output
    name: str = "cwyd"

class AppSettings(BaseSettings):
    """Root settings — composes all service settings."""
    model_config = SettingsConfigDict(env_file=".env")
    openai: AzureOpenAISettings = AzureOpenAISettings()
    search: AzureSearchSettings = AzureSearchSettings()
    database: DatabaseSettings = DatabaseSettings()
    orchestrator: Literal["openai_functions", "langgraph", "agent_framework"] = "langgraph"
    auth_type: Literal["rbac"] = "rbac"
    log_level: str = "INFO"
```

### 6.4 Assistant / Prompt Customization (active.json)

The assistant behavior, system prompts, and UI customization are controlled by `active.json`:

```json
{
  "orchestrator": {
    "strategy": "langgraph"
  },
  "prompts": {
    "system_message": "You are a helpful AI assistant...",
    "follow_up_questions_prompt": "Generate 3 follow-up questions...",
    "post_answering_prompt": "Validate the answer against the sources..."
  },
  "document_processors": [
    { "type": "pdf", "use_document_intelligence": true },
    { "type": "docx", "chunking_strategy": "layout" },
    { "type": "txt", "chunk_size": 500 }
  ],
  "ui": {
    "title": "Chat With Your Data",
    "logo_url": "/static/logo.png",
    "show_citations": true,
    "show_follow_up_questions": true
  }
}
```

### 6.5 Customization Points

| What to Customize | How | File(s) |
|---|---|---|
| **System prompt** | Edit `active.json` → `prompts.system_message` | `data/active.json` |
| **Orchestrator strategy** | Set `ORCHESTRATOR` env var or `active.json` | `.env` / `active.json` |
| **Database backend** | Set `databaseType` Bicep param at deploy time | `main.parameters.json` |
| **Chat model** | Set `AZURE_OPENAI_MODEL` env var | `.env` |
| **Embedding model** | Set `AZURE_OPENAI_EMBEDDING_MODEL` env var | `.env` |
| **Search behavior** | Modify `AzureSearchSettings` defaults or env vars | `env_settings.py` / `.env` |
| **Document processing** | Edit `active.json` → `document_processors` | `data/active.json` |
| **UI branding** | Edit `active.json` → `ui` section | `data/active.json` |
| **Add a new tool** | Implement tool in `shared/tools/`, register in orchestrator | `shared/tools/` |
| **Add a new orchestrator** | Extend `base.py`, register in `orchestrator.py` factory | `shared/orchestrator/` |
| **WAF-aligned deployment** | Enable `enableMonitoring`, `enableScalability`, `enableRedundancy`, `enablePrivateNetworking` | `main.parameters.json` |

### 6.6 Local Development Configuration

For local dev, all configuration comes from a `.env` file (generated by `azd env get-values` or manually created):

```bash
# .env (local development)
AZURE_OPENAI_ENDPOINT=https://your-ai-services.openai.azure.com/
AZURE_OPENAI_MODEL=gpt-4.1
AZURE_SEARCH_SERVICE=your-search-service
AZURE_SEARCH_INDEX=cwyd-index
AZURE_DB_TYPE=cosmosdb
AZURE_DB_ENDPOINT=https://your-cosmos.documents.azure.com:443/
AZURE_DB_NAME=cwyd
AZURE_STORAGE_BLOB_URL=https://your-storage.blob.core.windows.net/
AZURE_AI_PROJECT_ENDPOINT=https://your-foundry.services.ai.azure.com/
AZURE_CLIENT_ID=your-managed-identity-client-id
AZURE_TENANT_ID=your-tenant-id
```

---

## 7. Key Decisions

| Decision | Rationale |
|----------|-----------|
| **Foundry IQ** (Knowledge Base, Embeddings) for knowledge management; **LangChain / Agent Framework** for orchestration | Clean separation: knowledge management vs. agent logic |
| **Reasoning models** (o-series) enabled through Foundry IQ | Centralized model management; no per-orchestrator model wiring |
| **Infra is Phase 1** — every phase results in deployable `azd up` | Continuous validation, early issue detection, always-working baseline |
| **Azure Bot Service + Teams plugin** deferred to future version | Focus v2 on core modernization; extensibility built in for later |
| **Both Cosmos DB and PostgreSQL** kept as switchable backends | Preserves deployment flexibility for different enterprise needs |
| **Admin UI** merged into React/Vite frontend | Eliminates Streamlit dependency; unified user experience |
| **3 orchestrators** in v2: OpenAI Functions, LangGraph, Agent Framework | Covers direct tool calling, graph-based agents, and managed agent service |
| **`uv`** remains the Python package manager | Fast, modern, already adopted; Poetry fully removed |
| **No Key Vault for app secrets** | RBAC + Managed Identity; env vars from Bicep outputs (MACAE pattern) |
| **v2/src scaffolding** is a starting point — implement from scratch where needed | Don't assume scaffolding is complete or correct |

---

## 8. Deferred to Future Versions

- Azure Bot Service integration
- Microsoft Teams extension / plugin
- Additional Azure region support
- Advanced image processing (Computer Vision vectorization)
- MCP server integration
- Multi-agent coordination

---

## 9. Verification Criteria

1. `uv sync` succeeds with updated dependencies (no Poetry, no Semantic Kernel)
2. `pytest` passes for all three orchestrator strategies
3. FastAPI backend starts locally; `/api/health` returns 200
4. Conversation endpoint works through Foundry IQ (streaming + non-streaming)
5. Chat history CRUD works with both Cosmos DB and PostgreSQL
6. Admin pages render in the React frontend; document upload functional
7. Azure Functions pipeline processes blob uploads → embed → index
8. `azd up` deploys the full stack (no one-click button)
9. Frontend Jest tests pass
10. No references remain to Prompt Flow, Semantic Kernel, Streamlit, Poetry, or direct Azure OpenAI SDK
11. Every phase from 1–7 can be deployed independently via `azd up`
