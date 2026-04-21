# CWYD v2 — MVP Release Plan

**Target**: Ship a fully modernized Chat With Your Data accelerator that deploys end-to-end via `azd up`, with a FastAPI backend, LangGraph orchestrator, Foundry IQ integration, and support for both Cosmos DB and PostgreSQL.

**Date**: April 2026

---

## 1. MVP Milestones

> **Principle**: Every milestone ends with a working `azd up`. Each delivers a vertical slice — infra + data + backend + frontend — even if minimal.

### M1 — Infrastructure + Project Skeleton
> `azd up` → all Azure resources deployed, stub apps running, sample data loaded

| Deliverable | Description |
|---|---|
| Bicep infra | Clean modules with `databaseType` param (Cosmos DB or PostgreSQL) |
| Identity | User-assigned managed identity + RBAC roles (no Key Vault) |
| Foundry IQ | Resource deployed (knowledge base, embeddings, model deployments) |
| `azure.yaml` | v2 service paths (backend, frontend, functions) |
| Backend stub | FastAPI — `GET /api/health` returns 200 |
| Frontend stub | React placeholder page ("CWYD v2") |
| Containers | Dockerfiles for backend + frontend |
| Bootstrap | Post-deploy script loads sample data to Blob Storage |

### M2 — Configuration + LLM Integration
> `azd up` → configured backend, chat UI shell, all Azure connections validated

| Deliverable | Description |
|---|---|
| Pydantic Settings | Replaces `EnvHelper`; typed, validated, nested per service |
| Foundry IQ client | Knowledge base access + embeddings |
| Credential factory | Managed Identity (deployed) / Azure CLI (local) |
| Health check | Dependency validation (DB, search, Foundry IQ) |
| Frontend shell | Basic chat UI (input box, message list, layout) |
| `uv` project | Fully configured — `uv sync` installs everything |

### M3 — Conversation + RAG (Core Chat)
> `azd up` → working chat with streamed answers and citations from sample docs

| Deliverable | Description |
|---|---|
| Orchestrator router | Strategy pattern dispatch (OpenAI Functions, LangGraph, Agent Framework) |
| LangGraph agent | `StateGraph` + `ToolNode` orchestration graph |
| Agent Framework | Azure AI Agent Framework integration |
| Search handler | Azure AI Search (async) |
| Conversation API | `POST /api/conversation` — SSE streaming + non-streaming |
| Citations | Extraction and formatting from search results |
| Frontend chat | Connected to backend, consumes SSE stream |
| Index scripts | Create search index + index sample documents |

### M4 — Chat History + Both Databases
> `azd up` → persistent chat on either Cosmos DB or PostgreSQL

| Deliverable | Description |
|---|---|
| Cosmos DB history | Async CRUD client |
| PostgreSQL history | Async CRUD client |
| Database factory | Selects backend via `DATABASE_TYPE` env var |
| pgvector search | PostgreSQL vector search handler (async) |
| History API | CRUD, feedback, status endpoints |
| History panel | Frontend conversation list (select, rename, delete) |

### M5 — Admin + Frontend Merge
> `azd up` → full frontend with admin pages, auth, document management

| Deliverable | Description |
|---|---|
| Admin API | Settings, config, SAS tokens, orchestrator switching |
| Admin pages | React pages (ingestion, config, exploration) |
| Files router | Blob serving |
| Speech router | Azure Speech token |
| Auth | Router + middleware (RBAC, role-based admin access) |
| Cleanup | Remove all Streamlit references |

### M6 — RAG Indexing Pipeline
> `azd up` → end-to-end: upload document → functions process → index → chat

| Deliverable | Description |
|---|---|
| `batch_start` | List blobs, queue messages |
| `batch_push` | Parse, chunk, embed, push to search index |
| `add_url` | URL fetch, parse, embed |
| `search_skill` | Custom AI Search skill endpoint |
| Embedder factory | Push, PostgreSQL, integrated vectorization |
| PG vector indexing | LangChain PostgreSQL vector indexing |

### M7 — Testing + Documentation
> `azd up` → production-ready, fully tested and documented

| Deliverable | Description |
|---|---|
| Backend tests | pytest + pytest-asyncio covering all 3 orchestrators |
| Frontend tests | Jest tests for chat + admin features |
| Migration guide | v1 → v2 migration documentation |
| Updated docs | Configuration, deployment, orchestrator options |
| Final cleanup | Remove all Prompt Flow, Semantic Kernel, Poetry, direct OpenAI SDK refs |

---

## 2. Scope

### 2.1 In Scope

| Feature | Milestone | Notes |
|---|---|---|
| Clean Bicep infra (Cosmos DB / PostgreSQL) | M1 | `databaseType` parameter switches all DB resources |
| RBAC + Managed Identity (no Key Vault secrets) | M1 | MACAE pattern |
| Foundry IQ (Knowledge Base, Embeddings) | M1–M3 | Resource in M1, client in M2, integration in M3 |
| FastAPI backend (async) | M1–M3 | Stub in M1, config in M2, full in M3 |
| Pydantic Settings (typed config, no EnvHelper) | M2 | Layered: Bicep params → env vars → Pydantic → active.json |
| `uv` package manager | M2 | Replaces Poetry/pip |
| LangGraph orchestrator | M3 | `StateGraph` + `ToolNode` |
| Azure AI Agent Framework | M3 | Agent lifecycle, tool management, tracing |
| OpenAI Functions orchestrator | M3 | Kept, routed through Foundry IQ |
| SSE streaming | M3 | `POST /api/conversation` |
| Chat history (Cosmos DB + PostgreSQL) | M4 | Async CRUD, database factory |
| pgvector search | M4 | PostgreSQL vector search |
| Admin UI in React frontend | M5 | Replaces Streamlit |
| Auth middleware (RBAC) | M5 | Role-based admin access |
| Split Azure Functions pipeline | M6 | batch_start, batch_push, add_url, search_skill |
| Integrated vectorization | M6 | AI Search built-in vectorization |
| Comprehensive test suite | M7 | pytest + Jest |

### 2.2 Out of Scope (Deferred)

| Feature | Reason |
|---|---|
| Azure Bot Service | Focus v2 on core modernization |
| Microsoft Teams extension | Deferred to future version |
| Additional Azure region support | Post-MVP expansion |
| Advanced image processing (Computer Vision) | Post-MVP feature |
| MCP server integration | Future enhancement |
| Multi-agent coordination | Future Agent Framework capability |

---

## 3. Milestone Dependency Graph

```
M1 (Infra + Skeleton)               ← azd up: stub apps + all Azure resources
  │
  ▼
M2 (Config + LLM)                   ← azd up: configured backend, chat UI shell
  │
  ▼
M3 (Conversation + RAG)             ← azd up: working chat with streaming + citations
  │
  ├──────────┐
  │          │
  ▼          ▼
M4         M5
(History    (Admin +
 + DBs)     Frontend)
  │          │
  └────┬─────┘
       ▼
M6 (RAG Indexing Pipeline)           ← azd up: full ingestion + chat pipeline
       │
       ▼
M7 (Testing + Docs)                 ← azd up: production-ready
```

---

## 4. Release Criteria

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
11. Every milestone from M1–M7 can be deployed independently via `azd up`

---

## 5. Configuration & Customization

For full configuration architecture, layers, and customization points, see:
- **[modernization-plan.md § 7](modernization-plan.md#7-configuration--customization)** — Configuration layers, customization points table, local dev config
- **[development_plan.md § 6](../development_plan.md#6-configuration--customization)** — Detailed config architecture, Pydantic Settings examples, active.json schema

**Summary of configuration layers**:

| Layer | When Set | Example |
|---|---|---|
| Bicep Parameters | Deploy time (`azd up`) | `databaseType`, `gptModelName`, `enableMonitoring` |
| Environment Variables | Deploy time (Bicep outputs) | `AZURE_OPENAI_ENDPOINT`, `AZURE_DB_ENDPOINT` |
| Pydantic Settings | Runtime (loaded from env) | `AppSettings.search.top_k`, `AppSettings.openai.temperature` |
| active.json | Runtime (hot-reloadable) | System prompt, document processors, UI branding |

---

## 6. Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Azure AI Agent Framework SDK still in preview | API changes may require rework | Pin version, abstract behind interface, monitor for GA |
| LangGraph 0.4+ breaking changes | Orchestrator rework | Pin version, use stable API surface only |
| Foundry IQ API changes | Knowledge base / embeddings client rework | Abstract client behind factory, isolate in `shared/llm/` |
| Both-DB support doubles test surface | Slower M4 delivery | Database factory pattern, shared test fixtures, parallel CI |
| Admin UI complexity in React | M5 takes longer than expected | Start with minimal admin (upload + status), iterate |
| Infra-first approach may surface Azure quota limits early | M1 blocked | Run quota check script pre-deploy; document required quotas |

---

## 7. Related Documents

| Document | Description |
|---|---|
| [modernization-plan.md](modernization-plan.md) | Library upgrades, architecture changes, migration strategy |
| [development_plan.md](../development_plan.md) | Detailed task-level implementation plan (53 tasks across 7 phases) |
