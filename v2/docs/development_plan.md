# CWYD v2 — Development Plan Proposal

**Repo**: [Azure-Samples/chat-with-your-data-solution-accelerator](https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator)
**Branch**: `dev-v2`
**Date**: April 2026

---

## Summary

Modernize the Chat With Your Data Solution Accelerator from a monolithic Flask application with four co-installed orchestrators into a modular **FastAPI + Azure Functions** architecture. Replace the direct Azure OpenAI SDK with **Foundry IQ** as the model gateway, remove Prompt Flow, Semantic Kernel, Streamlit admin, one-click deploy, and Poetry references, add the **Azure AI Agent Framework** with reasoning model support, upgrade **LangChain to LangGraph** for PostgreSQL indexing, and split **Azure Functions** into a modular RAG indexing pipeline. Azure Bot Service and Teams plugin are deferred to a future version.

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
| **Direct Azure OpenAI SDK** | Replaced by Foundry IQ as the model gateway |
| **Azure Bot Service / Teams extension** | Deferred to a future version |

### 2.2 Additions

| Component | Purpose |
|-----------|---------|
| **Azure AI Agent Framework** | Modern agent orchestration — replaces Semantic Kernel and Prompt Flow |
| **Foundry IQ** | Model gateway for Azure OpenAI: GPT-\*, reasoning models (o-series), embeddings |
| **Reasoning model support** | o-series reasoning models routed through Foundry IQ |

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
              ┌────────▼───┐  ┌─────▼──────┐  ┌────▼─────────────┐
              │ Orchestrator│  │ Chat       │  │  Foundry IQ      │
              │ Router      │  │ History    │  │  (Model Gateway)  │
              │             │  │ CosmosDB   │  │  ├─ GPT-*        │
              │ ┌─────────┐ │  │ or         │  │  ├─ o-series     │
              │ │LangGraph│ │  │ PostgreSQL │  │  │  (reasoning)  │
              │ └─────────┘ │  └────────────┘  │  └─ Embeddings  │
              │ ┌─────────┐ │                  └──────────────────┘
              │ │Agent    │ │
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
OpenAI Functions      ──────────▶  OpenAI Functions (kept, via Foundry IQ)
Semantic Kernel       ─────╳────▶  REMOVED
LangChain Agent       ──────────▶  LangGraph Agent (upgraded)
Prompt Flow           ─────╳────▶  REMOVED
                                   Agent Framework (NEW)

Model Access:
v1: Direct Azure OpenAI SDK  ──▶  v2: Foundry IQ (gateway)
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
│       │   └── llm_helper.py     # Foundry IQ client wrapper
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
```

---

## 4. Implementation Phases

### Phase 1 — Foundation (Backend Core + Configuration)

**Goal**: Bootable FastAPI backend with health check, configuration system, and Foundry IQ integration.

| # | Task | Key Files |
|---|------|-----------|
| 1 | FastAPI app factory with lifespan, CORS, OpenTelemetry | `backend/app.py` |
| 2 | Pydantic `BaseSettings` replacing `EnvHelper` (nested models per Azure service) | `shared/config/env_settings.py` |
| 3 | Foundry IQ client integration replacing direct Azure OpenAI SDK | `shared/llm/llm_helper.py` |
| 4 | Health router with dependency checks | `backend/routers/health.py` |
| 5 | Dependency injection wiring | `backend/dependencies.py` |

### Phase 2 — Conversation + Chat History

**Goal**: Working conversation endpoint with chat history persistence. *Depends on Phase 1.*

| # | Task | Key Files |
|---|------|-----------|
| 6 | Conversation router (streaming + non-streaming, BYOD + custom) | `backend/routers/conversation.py` |
| 7 | Orchestrator router / factory (strategy pattern dispatch) | `shared/orchestrator/orchestrator.py` |
| 8 | OpenAI Functions orchestrator (tool calling via Foundry IQ) | `shared/orchestrator/openai_functions.py` |
| 9 | Shared tools layer (QA, text processing, content safety, post-prompt) | `shared/tools/*` |
| 10 | Chat history — Cosmos DB + PostgreSQL clients | `shared/chat_history/*` |
| 11 | Chat history router (CRUD, feedback, status) | `backend/routers/chat_history.py` |

### Phase 3 — Alternative Orchestrators

**Goal**: LangGraph and Agent Framework orchestrators operational. *Depends on Phase 2.*

| # | Task | Key Files |
|---|------|-----------|
| 12 | LangGraph agent — `StateGraph` + `ToolNode`, LangChain PostgreSQL indexing | `shared/orchestrator/langgraph_agent.py` |
| 13 | Azure AI Agent Framework orchestrator | `shared/orchestrator/azure_agents.py` |
| 14 | Reasoning model support via Foundry IQ (o-series model routing) | `shared/llm/llm_helper.py` |

### Phase 4 — Admin + Frontend Merge

**Goal**: Unified React/Vite frontend with admin capabilities. *Depends on Phase 2 for API.*

| # | Task | Key Files |
|---|------|-----------|
| 15 | Admin pages in React frontend (data ingestion, config, exploration) | `frontend/src/pages/admin/` |
| 16 | Admin API router (settings, config, SAS tokens, orchestrator switching) | `backend/routers/admin.py` |
| 17 | Files router (blob serving), speech router (Azure Speech token) | `backend/routers/files.py`, `speech.py` |
| 18 | Auth router | `backend/routers/auth.py` |

### Phase 5 — RAG Indexing Functions (Split)

**Goal**: Modular Azure Functions for the document processing pipeline. *Depends on Phase 1.*

| # | Task | Key Files |
|---|------|-----------|
| 19 | `batch_start` — list blobs, queue messages | `functions/blueprints/batch_start.py` |
| 20 | `batch_push` — parse, chunk, embed, push to search index | `functions/blueprints/batch_push.py` |
| 21 | `add_url` — URL fetch, parse, embed | `functions/blueprints/add_url.py` |
| 22 | `search_skill` — custom AI Search skill endpoint | `functions/blueprints/search_skill.py` |
| 23 | LangChain PostgreSQL vector indexing integration | `shared/search/postgres_handler.py` |
| 24 | Embedder factory + implementations (push, postgres, integrated vectorization) | `shared/embedders/*` |

### Phase 6 — Infrastructure + Deployment

**Goal**: Updated Bicep + azd config. No one-click deploy.

| # | Task | Key Files |
|---|------|-----------|
| 25 | Update Bicep — add Foundry IQ resource, remove Azure ML / Prompt Flow | `infra/main.bicep`, `infra/modules/` |
| 26 | Remove one-click "Deploy to Azure" button and ARM template references | `README.md` |
| 27 | Update `azure.yaml` for v2 service paths | `azure.yaml` |
| 28 | Update Dockerfiles for v2 structure; remove Streamlit admin Dockerfile | `docker/` |
| 29 | Remove Poetry references from all config and docs | project-wide |

### Phase 7 — Testing + Documentation

**Goal**: Comprehensive test coverage and updated documentation.

| # | Task | Key Files |
|---|------|-----------|
| 30 | Port / rewrite pytest tests for FastAPI (`TestClient`), cover all 3 orchestrators | `tests/` |
| 31 | Update frontend Jest tests for admin features | `frontend/` |
| 32 | Update README with new architecture and setup instructions | `README.md` |
| 33 | Write v2 migration guide | `v2/docs/` |
| 34 | Update docs for new configuration, deployment, and orchestrator options | `docs/` |

---

## 5. Phase Dependency Graph

```
Phase 1 (Foundation)
  │
  ├──────────────────────┐
  │                      │
  ▼                      ▼
Phase 2 (Conversation)  Phase 5 (Functions)
  │
  ├──────────┐
  │          │
  ▼          ▼
Phase 3    Phase 4
(Orch.)    (Admin + FE)
  │          │
  └────┬─────┘
       ▼
Phase 6 (Infra + Deploy)
       │
       ▼
Phase 7 (Testing + Docs)
```

---

## 6. Key Decisions

| Decision | Rationale |
|----------|-----------|
| **Foundry IQ** is the model gateway; **LangChain / Agent Framework** handle orchestration | Clean separation of concerns: model routing vs. agent logic |
| **Reasoning models** (o-series) enabled through Foundry IQ | Centralized model management; no per-orchestrator model wiring |
| **Azure Bot Service + Teams plugin** deferred to future version | Focus v2 on core modernization; extensibility built in for later |
| **Both Cosmos DB and PostgreSQL** kept as switchable backends | Preserves deployment flexibility for different enterprise needs |
| **Admin UI** merged into React/Vite frontend | Eliminates Streamlit dependency; unified user experience |
| **3 orchestrators** in v2: OpenAI Functions, LangGraph, Agent Framework | Covers direct tool calling, graph-based agents, and managed agent service |
| **`uv`** remains the Python package manager | Fast, modern, already adopted; Poetry fully removed |
| **v2/src scaffolding** is a starting point — implement from scratch where needed | Don't assume scaffolding is complete or correct |

---

## 7. Deferred to Future Versions

- Azure Bot Service integration
- Microsoft Teams extension / plugin
- Additional Azure region support
- Advanced image processing (Computer Vision vectorization)

---

## 8. Verification Criteria

1. `uv sync` succeeds with updated dependencies (no Poetry, no Semantic Kernel)
2. `pytest` passes for all three orchestrator strategies
3. FastAPI backend starts locally; `/api/health` returns 200
4. Conversation endpoint works through Foundry IQ (streaming + non-streaming)
5. Chat history CRUD works with both Cosmos DB and PostgreSQL
6. Admin pages render in the React frontend; document upload functional
7. Azure Functions pipeline processes blob uploads → embed → index
8. `azd up` deploys the full stack without one-click button
9. Frontend Jest tests pass
10. No references remain to Prompt Flow, Semantic Kernel, Streamlit, Poetry, or direct Azure OpenAI SDK
