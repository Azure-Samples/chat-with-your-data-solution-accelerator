# CWYD v2 — Development Plan

**Repo**: [Azure-Samples/chat-with-your-data-solution-accelerator](https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator)
**Branch**: `dev-v2`
**Last updated**: April 27, 2026

---

## 0. Status snapshot

Where we are against the 7-phase plan in §4. Status legend: ✅ done · ⏳ in progress · ⏭ next · ☐ not started.

| Phase | Title | Status | Notes |
|---|---|---|---|
| 1 | Infrastructure + Project Skeleton | ✅ done | Bicep ✅ (AVM-first, UAMI+RBAC, no Key Vault, two-mode `databaseType`, P1 polish shipped). Backend / frontend / functions stubs ☐. |
| 2 | Configuration + LLM Integration | ⏭ next | `shared/registry.py` + 11/11 tests ✅ (Phase 2 prerequisite). `shared/settings.py` is the next unit. |
| 3 | Conversation + RAG (Core Chat) | ☐ | |
| 4 | Chat History + Both Databases | ☐ | |
| 5 | Admin + Frontend Merge | ☐ | |
| 6 | RAG Indexing Pipeline (Split Functions) | ☐ | |
| 7 | Testing + Documentation | ☐ | Rolling — each phase ends with `azd up` green and updates this file. |

See §10 for the file-level inventory of work already shipped.

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

> **On-disk layout** (already adopted; replaces the earlier "everything-under-`shared/`" sketch). Cross-cutting **primitives** live in `shared/`. Every **swappable concern** lives under `providers/<domain>/` and is wired through the registry pattern in §3.5. **Composed flows** that wire providers together live in `pipelines/`.

```
v2/
├── src/
│   ├── shared/                       # primitives only — NOT pluggable
│   │   ├── registry.py               # generic Registry[T]                     [done]
│   │   ├── settings.py               # Pydantic AppSettings (Bicep outputs)    [Phase 2]
│   │   ├── types.py                  # OrchestratorEvent, Citation, SearchResult
│   │   ├── observability.py          # OTel + App Insights wiring
│   │   └── tools/                    # cross-cutting helpers (content_safety, post_prompt)
│   │
│   ├── providers/                    # registry-keyed plug-ins (§3.5)
│   │   ├── credentials/              # managed_identity · cli
│   │   ├── llm/                      # foundry_iq
│   │   ├── embedders/                # foundry_kb · pgvector
│   │   ├── parsers/                  # pdf · docx · html · md · txt
│   │   ├── search/                   # azure_search · pgvector · integrated_vectorization
│   │   ├── chat_history/             # cosmosdb · postgres
│   │   └── orchestrators/            # langgraph · agent_framework
│   │
│   ├── pipelines/                    # composed flows — NOT pluggable
│   │   ├── ingestion.py              # parse → chunk → embed → index
│   │   └── chat.py                   # user msg → orchestrator → SSE
│   │
│   ├── backend/                      # FastAPI app    (azd service)
│   │   ├── app.py                    # App factory, lifespan, CORS, OpenTelemetry
│   │   ├── dependencies.py           # DI (settings, providers, credentials)
│   │   ├── routers/                  # conversation · admin · chat_history · files · speech · auth · health
│   │   └── models/                   # Pydantic request/response models
│   │
│   ├── functions/                    # Azure Functions app    (azd service)
│   │   ├── function_app.py           # blueprint registration
│   │   └── blueprints/               # batch_start · batch_push · add_url · search_skill
│   │
│   ├── frontend/                     # React + Vite (Chat + Admin merged)    (azd service)
│   │   └── src/
│   │       ├── pages/                # chat/  admin/
│   │       ├── stores/               # Zustand state
│   │       └── api/                  # generated OpenAPI client
│   │
│   └── config_assets/                # data, not code
│       ├── default.json              # default orchestrator/tools/chunking config
│       └── schemas/                  # JSON schemas validating default.json + active.json
│
├── infra/                            # Bicep + AVM modules                  [done]
│   ├── main.bicep                    # entry point with databaseType param
│   ├── main.parameters.json
│   ├── main.waf.parameters.json
│   └── modules/                      # ai-project, ai-project-search-connection, virtualNetwork (custom; rest are AVM)
│
├── docker/                           # Dockerfiles + docker-compose dev stack
├── scripts/                          # post_provision.{sh,ps1,py}
├── azure.yaml                        # azd manifest
├── pyproject.toml                    # uv project root for v2                [done]
└── tests/                            # mirrors src/
    ├── conftest.py                                                          [done]
    ├── shared/                       # test_registry.py [done] + test_settings.py [Phase 2]
    ├── providers/                    # one folder per registered domain
    ├── pipelines/
    ├── backend/routers/
    └── functions/blueprints/
```

**Why this layout** (rather than the older monolithic `shared/{orchestrator,llm,embedders,...}/` tree):

1. **`shared/` becomes small and obvious** — only true cross-cutting primitives (registry, settings, types, observability, helper tools). Easier to reason about, easier to test.
2. **`providers/` makes "what's pluggable" explicit** — every subfolder is a registry-keyed domain with the same recipe (§3.5). Adding a new provider = drop a file + 1 import in `__init__.py`. No grep across `shared/` to find the plug-in surface.
3. **`pipelines/` separates orchestration from plug-points** — ingestion and chat are *composed code* that wires providers together, not providers themselves. They have one implementation each and don't belong in a registry.
4. **`backend/`, `functions/`, `frontend/` stay top-level under `src/`** — matches azd convention, keeps Dockerfile contexts simple, keeps `azure.yaml` service paths short.
5. **`config_assets/`** — default config JSON + JSON schemas are *data*, not code. Keeping them out of `shared/` keeps the code tree clean.

### 3.5 Pluggability contract (registry-first) — stated once, referenced from every phase

Every swappable concern in v2 (credentials, llm, embedders, parsers, search, chat_history, orchestrators) follows the **same** registry recipe — driven by the generic `Registry[T]` primitive in [`v2/src/shared/registry.py`](../src/shared/registry.py).

#### 3.5.1 The recipe (3 files per domain)

```python
# v2/src/providers/<domain>/base.py
from abc import ABC, abstractmethod

class Base<Domain>(ABC):
    @abstractmethod
    async def do_thing(self, ...): ...
```

```python
# v2/src/providers/<domain>/__init__.py
from shared.registry import Registry
from .base import Base<Domain>

registry: Registry[type[Base<Domain>]] = Registry("<domain>")

from . import provider_a, provider_b   # eager import — triggers @register

def create(key: str, **kwargs) -> Base<Domain>:
    return registry.get(key)(**kwargs)
```

```python
# v2/src/providers/<domain>/provider_a.py
from . import registry
from .base import Base<Domain>

@registry.register("a")
class ProviderA(Base<Domain>):
    def __init__(self, settings, ...): ...
    async def do_thing(self, ...): ...
```

**Caller code is one line** anywhere in the codebase:

```python
from providers import embedders
embedder = embedders.create(settings.database.index_store, settings=settings, llm=llm)
```

#### 3.5.2 Two anti-patterns are banned

1. **`if/elif` over provider names anywhere outside a `Registry[T]`.** Forbidden by Hard Rule #4 in [`copilot-instructions.md`](../../.github/copilot-instructions.md). Greppable: `grep -rn "if .*== .['\"]cosmosdb['\"]"` must return 0 hits in `v2/src/`.
2. **Lazy in-function imports of provider classes.** Imports happen once per domain in `__init__.py`. A function body never `import`s a provider.

#### 3.5.3 How to add new tech in 3 steps (uniform across domains)

| Want to add… | Step 1 | Step 2 | Step 3 |
|---|---|---|---|
| **A new orchestrator** (e.g., CrewAI) | Create `v2/src/providers/orchestrators/crewai.py` with `class CrewAIOrchestrator(OrchestratorBase)` | Decorate the class: `@registry.register("crewai")` | Add `from . import crewai` to `providers/orchestrators/__init__.py` |
| **A new chat-history backend** (e.g., Redis) | Create `v2/src/providers/chat_history/redis.py` with `class RedisChatHistory(BaseChatHistory)` | `@registry.register("redis")` | Add `from . import redis` to `providers/chat_history/__init__.py` |
| **A new embedder** (e.g., local sentence-transformers) | Create `v2/src/providers/embedders/sentence_transformers.py` | `@registry.register("sentence_transformers")` | Add `from . import sentence_transformers` to `providers/embedders/__init__.py` |

No central factory file to edit. No `if/elif` chain to extend. The new provider is selectable by setting the corresponding env var (e.g., `AZURE_DB_TYPE=redis`).

#### 3.5.4 What the registry buys CWYD at multi-container scale

- **Per-container imports.** Backend imports `providers/orchestrators/`, `providers/chat_history/`, `providers/search/`. Functions imports `providers/embedders/`, `providers/parsers/`, `providers/search/`. Heavy SDKs (`azure-ai-projects`, `langgraph`, `psycopg`) load only where used — smaller cold starts, smaller images, lower memory per replica.
- **Independent deployment.** Each azd service ships only the providers it needs; adding a provider in one service has zero impact on the other.
- **Scenario Pack / Customization Layer plug-ins** can ship out-of-tree: a customer fork drops `providers/embedders/customer_aoai.py` with `@register("customer_aoai")` — no upstream patch required.
- **Configuration-driven swaps.** The provider key *is* the config value (`settings.database.db_type` → `chat_history.create(...)`). No drift between config strings and dispatch labels.

See §3.6 below for the parallel rule applied to **infrastructure** modules.

### 3.6 Infrastructure extensibility (parallel of §3.5 for Bicep)

The Bicep infra (`v2/infra/`) follows three rules so adding a new backend (DB, search, AI service) costs the same as adding a new code provider:

#### 3.6.1 Three rules

1. **Each pluggable backend is its own Bicep module** under `infra/modules/` (or AVM module under `br/public:avm/...`). Each module exposes a **uniform output contract**: `endpoint` URI, `resourceId`, and `principalIdsToGrantRbac` (list of UAMI principal IDs the module wires into its data-plane RBAC). This mirrors how `BaseLLMProvider` looks the same across `foundry_iq` / future providers.
2. **Single dispatch point.** `main.bicep` selects backends via the `databaseType` param (today: `cosmosdb` | `postgresql`). Adding a third mode (e.g., `mongodb`) means: add the allowed value, instantiate one conditional module, expose its outputs to the same env-var names. **No other file changes** — backend code reads the same `AZURE_*` env vars regardless of mode.
3. **WAF flags never branch topology, only sizing.** The four flags (`enableMonitoring`, `enableScalability`, `enableRedundancy`, `enablePrivateNetworking`) only adjust SKU / replica count / VNet integration on existing resources. Adding a new resource means deciding *how it responds to each flag*, not duplicating the resource per flag.

#### 3.6.2 Phase 1 follow-up — P1 polish tweaks (✅ shipped 2026-04-27)

From the infra audit (8.5/10, AVM coverage ≈95%); landed alongside the next Phase 2 unit so `AzurePostgresSettings` reads a single URI from day one:

| # | Tweak | File | Status |
|---|---|---|---|
| P1.1 | Added `AZURE_POSTGRES_ENDPOINT` Bicep output (full `postgresql://<fqdn>:5432/cwyd?sslmode=require` URI form, no credentials — the workload supplies an Entra token; the user comes from `AZURE_UAMI_CLIENT_ID`). Mirrors `AZURE_COSMOS_ENDPOINT` shape. | `infra/main.bicep` | ✅ |
| P1.2 | Validate `postgresAdminPrincipalName` non-empty when `databaseType == 'postgresql'` via a fail-fast `_validatePostgresAdminPrincipalName` guard variable that aborts ARM expansion before any resource is provisioned. | `infra/main.bicep` | ✅ |
| P1.3 | Refreshed `enablePrivateNetworking` description — work is complete (VNet + private DNS + private endpoints + regional VNet integration + Bastion all wired); flag is the supported WAF-aligned topology. | `infra/main.bicep` | ✅ |

---

## 4. Implementation Phases

> **Principle**: Every phase ends with a working `azd up`. Each phase delivers a vertical slice: infra + data + backend + frontend — even if minimal. This ensures continuous deployability and early validation.

### Phase 1 — Infrastructure + Project Skeleton

**Goal**: `azd up` deploys all Azure resources and stub applications. A browser can hit the frontend and see a placeholder page; the backend responds to `/api/health`.

| # | Task | Key Files | Status |
|---|---|---|---|
| 1 | Clean Bicep infra with `databaseType` parameter (Cosmos DB or PostgreSQL); follows §3.6 uniform output contract | `infra/main.bicep`, `infra/modules/` | ✅ |
| 2 | User-assigned managed identity + RBAC roles (no Key Vault secrets) | `infra/main.bicep` (UAMI inline + role assignments per AVM) | ✅ |
| 3 | Foundry IQ resource (AI Services account, Foundry Project, model deployments) | `infra/modules/ai-project.bicep`, `infra/modules/ai-project-search-connection.bicep` | ✅ |
| 4 | `azure.yaml` with v2 service paths (backend, frontend, functions) | `azure.yaml` | ✅ |
| 5 | Stub FastAPI backend — `GET /api/health` returns 200 | `src/backend/app.py`, `src/backend/routers/health.py` | ☐ |
| 6 | Stub React frontend — placeholder page with "CWYD v2" | `src/frontend/src/` | ☐ |
| 7 | Dockerfiles for backend + frontend | `docker/` | ⏳ partial |
| 8 | Post-deploy script — loads sample data + default config to Blob Storage | `scripts/post_provision.{sh,ps1,py}` | ⏳ partial |
| 9 | Sample documents for bootstrap | `data/` (root) | ✅ |
| P1.1–3 | P1 polish tweaks (§3.6.2) | `infra/main.bicep` | ✅ |

**`azd up` result**: All infra provisioned, stub apps running in Azure, sample data loaded, health check passes.

### Phase 2 — Configuration + LLM Integration

**Goal**: Backend has a real configuration system, connects to Foundry IQ, and health check validates all dependencies. Frontend shows a basic chat shell (no backend integration yet).

All provider work in this phase follows the registry recipe in §3.5.

| # | Task | Key Files | Status |
|---|---|---|---|
| 2.0 | Generic `Registry[T]` primitive (Phase 2 prerequisite) | `src/shared/registry.py` + `tests/shared/test_registry.py` | ✅ (11/11) |
| 10 | Pydantic `AppSettings` replacing `EnvHelper` (nested models per Azure service; reads every Bicep output env var; cached `get_settings()`) | `src/shared/settings.py` + `tests/shared/test_settings.py` | ⏭ next |
| 11 | Credentials providers (registry domain): `BaseCredentialFactory` ABC + `managed_identity` + `cli` | `src/providers/credentials/{base,managed_identity,cli,__init__}.py` | ☐ |
| 12 | LLM provider (registry domain): `BaseLLMProvider` ABC + `foundry_iq` (AIProjectClient-backed; methods `chat`, `chat_stream`, `embed`, `reason`) | `src/providers/llm/{base,foundry_iq,__init__}.py` | ☐ |
| 13 | Health router with dependency checks (DB, search, Foundry IQ connectivity) — reads providers via DI | `src/backend/routers/health.py` | ☐ |
| 14 | Dependency injection wiring (settings + credentials + llm registries → routers) | `src/backend/dependencies.py` | ☐ |
| 15 | Frontend: basic chat UI shell (input box, message list, layout) | `src/frontend/src/pages/chat/` | ☐ |
| 16 | Bicep outputs wired to backend env vars (no Key Vault) | `infra/main.bicep` outputs section | ✅ |

**`azd up` result**: Configured backend with detailed health check, frontend shell visible, all Azure service connections validated.

### Phase 3 — Conversation + RAG (Core Chat)

**Goal**: A user can type a message and get a streamed answer grounded in indexed documents. This is the first "it works!" moment.

Orchestrators and search providers follow the registry recipe in §3.5. Caller code is `orchestrators.create(settings.orchestrator, ...)` and `search.create(settings.database.index_store, ...)` — no `if/elif` dispatch.

| # | Task | Key Files | Status |
|---|---|---|---|
| 17 | Orchestrator domain registry + `OrchestratorBase` ABC (async `run()` yielding `OrchestratorEvent`) | `src/providers/orchestrators/{base,__init__}.py` | ☐ |
| 18 | LangGraph orchestrator (`StateGraph` + `ToolNode`); `@register("langgraph")` | `src/providers/orchestrators/langgraph.py` | ☐ |
| 19 | Azure AI Agent Framework orchestrator; `@register("agent_framework")` | `src/providers/orchestrators/agent_framework.py` | ☐ |
| 20 | Cross-cutting tool helpers (QA, text processing, content safety, post-prompt). Tools are NOT a registry domain — they are imported directly. | `src/shared/tools/*` | ☐ |
| 21 | Search domain: `BaseSearch` ABC + `azure_search` provider (async); `@register("azure_search")` | `src/providers/search/{base,azure_search,__init__}.py` | ☐ |
| 22 | Conversation router (streaming SSE + non-streaming, BYOD + custom); composes `orchestrators.create(...)` | `src/backend/routers/conversation.py`, `src/pipelines/chat.py` | ☐ |
| 23 | Citation extraction and formatting | `src/shared/types.py` (Citation), tool helpers | ☐ |
| 24 | Frontend: chat connected to `/api/conversation`, SSE stream consumption (channels: `reasoning`, `tool`, `answer`, `citation`, `error`) | `src/frontend/src/pages/chat/` | ☐ |
| 25 | Reasoning model support via Foundry IQ (o-series routing in `foundry_iq.reason()`) | `src/providers/llm/foundry_iq.py` | ☐ |
| 26 | Scripts: create search index + index sample documents | `scripts/post_provision.py` | ☐ |

**`azd up` result**: Working chat experience — user asks a question, gets a streamed answer with citations from sample documents.

### Phase 4 — Chat History + Both Databases

**Goal**: Conversations persist across sessions. Both Cosmos DB and PostgreSQL work as chat history backends. pgvector search enabled for PostgreSQL deployments.

Chat history and search-pgvector are registry domains (§3.5). Picking the backend is one line: `chat_history.create(settings.database.db_type, ...)`.

| # | Task | Key Files | Status |
|---|---|---|---|
| 27 | Chat history domain: `BaseChatHistory` ABC + `cosmosdb` provider (async); `@register("cosmosdb")` | `src/providers/chat_history/{base,cosmosdb,__init__}.py` | ☐ |
| 28 | `postgres` chat-history provider (async); `@register("postgres")` | `src/providers/chat_history/postgres.py` | ☐ |
| 29 | Caller wiring — backend reads `chat_history.create(settings.database.db_type, ...)` (no `database_factory.py`; the registry IS the factory) | `src/backend/dependencies.py` | ☐ |
| 30 | `pgvector` search provider (async); `@register("pgvector")` | `src/providers/search/pgvector.py` | ☐ |
| 31 | Chat history router (CRUD, feedback, status) | `src/backend/routers/chat_history.py` | ☐ |
| 32 | Frontend: conversation history panel (list, select, rename, delete) | `src/frontend/src/pages/chat/` | ☐ |
| 33 | (Phase 4 is for backends; Agent Framework was added in Phase 3 §19.) | — | — |
| 34 | Bicep: ensure both DB conditional modules output the same env-var names per §3.6 contract | `infra/main.bicep` | ✅ |

**`azd up` result**: Chat with persistent history — user returns later and sees previous conversations. Works with either database type.

### Phase 5 — Admin + Frontend Merge

**Goal**: Unified frontend with admin capabilities. Document management, system status, configuration view — all inside the React app.

| # | Task | Key Files | Status |
|---|---|---|---|
| 35 | Admin API router (settings, config, SAS tokens, orchestrator switching via `settings.orchestrator`) | `src/backend/routers/admin.py` | ☐ |
| 36 | Admin pages in React frontend (data ingestion, config, exploration) | `src/frontend/src/pages/admin/` | ☐ |
| 37 | Files router (blob serving) | `src/backend/routers/files.py` | ☐ |
| 38 | Speech router (Azure Speech token) | `src/backend/routers/speech.py` | ☐ |
| 39 | Auth router + middleware (RBAC, role-based admin access) | `src/backend/routers/auth.py` | ☐ |
| 40 | Confirm no Streamlit references remain (v1 admin permanently removed per §2.1) | project-wide | ☐ |

**`azd up` result**: Full frontend with chat + admin pages. Users can upload documents, view system config, check index status — all in one app.

### Phase 6 — RAG Indexing Pipeline (Split Functions)

**Goal**: Modular Azure Functions process uploaded documents end-to-end: blob → parse → chunk → embed → index. Completes the full ingestion loop.

Parsers and embedders are registry domains (§3.5). The blueprint invokes `pipelines.ingestion.run(...)`; the pipeline uses `parsers.create(file_type, ...)` and `embedders.create(settings.database.index_store, ...)`. No parse/chunk/embed code lives in the blueprint.

| # | Task | Key Files | Status |
|---|---|---|---|
| 41 | Function app shell + `batch_start` blueprint (list blobs, queue per-doc messages) | `src/functions/function_app.py`, `src/functions/blueprints/batch_start.py` | ☐ |
| 42 | `batch_push` blueprint (queue trigger → `pipelines.ingestion.run`) | `src/functions/blueprints/batch_push.py` | ☐ |
| 43 | `add_url` blueprint (queue trigger; URL fetch → ingestion pipeline) | `src/functions/blueprints/add_url.py` | ☐ |
| 44 | `search_skill` blueprint (HTTP trigger; custom AI Search skill endpoint) | `src/functions/blueprints/search_skill.py` | ☐ |
| 45 | Parsers domain: `BaseParser` ABC + 5 providers (`pdf`, `docx`, `html`, `md`, `txt`); each `@register("<ext>")` | `src/providers/parsers/{base,pdf,docx,html,md,txt,__init__}.py` | ☐ |
| 46 | Embedders domain: `BaseEmbedder` ABC + 2 providers (`foundry_kb` Knowledge-Base upsert, `pgvector` chunk+embed+insert); each `@register("<key>")` | `src/providers/embedders/{base,foundry_kb,pgvector,__init__}.py` | ☐ |
| 47 | Ingestion pipeline (composes parsers + embedders; NOT a registry) | `src/pipelines/ingestion.py` | ☐ |
| 48 | Default config + post-provision (`config_assets/default.json`, `ConfigHelper.ensure_default_uploaded`, `scripts/post_provision.py` hook) | `src/config_assets/default.json`, `src/shared/config_helper.py`, `scripts/post_provision.py` | ☐ |

**`azd up` result**: End-to-end pipeline — upload a document via admin UI → functions process it → document appears in search → user can chat about it.

### Phase 7 — Testing + Documentation

**Goal**: Comprehensive test coverage, migration guide, and updated documentation.

| # | Task | Key Files | Status |
|---|---|---|---|
| 49 | Pytest suite for FastAPI (`httpx.AsyncClient` + `ASGITransport`); cover both orchestrators end-to-end via fakes | `tests/backend/`, `tests/providers/orchestrators/` | ☐ |
| 50 | Update frontend Jest/Vitest tests for admin features | `src/frontend/` | ☐ |
| 51 | Update root `README.md` with v2 architecture + setup; add `v2/README.md` quickstart | `README.md`, `v2/README.md` | ☐ |
| 52 | Write v2 migration guide | `v2/docs/migration.md` | ☐ |
| 53 | Update docs for new configuration, deployment, and orchestrator options | `v2/docs/`, `docs/` | ☐ |
| 54 | Confirm no references remain to Prompt Flow, Semantic Kernel, Streamlit, Poetry, direct Azure OpenAI SDK, one-click deploy (greppable gates) | project-wide | ☐ |

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
| **Add a new tool** | Implement helper in `shared/tools/`, import where needed (tools are not a registry domain) | `src/shared/tools/` |
| **Add a new orchestrator** | Follow §3.5 recipe: subclass `OrchestratorBase`, decorate with `@registry.register("<key>")`, add `from . import <module>` to `__init__.py` | `src/providers/orchestrators/` |
| **Add a new chat-history backend / search / embedder / parser / credential** | Same §3.5 recipe under the matching `providers/<domain>/` folder | `src/providers/<domain>/` |
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
12. **Greppable pluggability gates** (added by §3.5):
    - `grep -rn "if .*== .['\"]\(cosmosdb\|postgres\|langgraph\|agent_framework\|foundry_iq\|pgvector\)['\"]" v2/src/` returns 0 hits outside `tests/` (no `if/elif` provider dispatch).
    - No `import` of a provider class inside a function body in `v2/src/{backend,functions,pipelines}/**` (registries handle provider loading).

---

## 10. Inventory of done work

> Single source of truth for what is already shipped, so no agent re-does work that's complete. Update this section whenever a phase task lands.

### 10.1 Phase 0 — Workspace foundations (✅ done)

| File | Purpose |
|---|---|
| [`v2/pyproject.toml`](../pyproject.toml) | uv project root for v2 (Python ≥3.11; deps include fastapi, azure-functions, azure-ai-projects, azure-ai-agents, langgraph, langchain-openai, azure-identity, azure-storage-blob/queue, azure-cosmos, asyncpg, psycopg2-binary, pgvector, azure-monitor-opentelemetry, pydantic-settings; dev: pytest, pytest-asyncio, pytest-cov). |
| [`v2/.venv/`](../.venv) | v2-scoped venv (Python 3.13.13, 141 packages via `uv sync`). |
| [`v2/.vscode/settings.json`](../.vscode/settings.json) | Pinned interpreter `${workspaceFolder}/v2/.venv/Scripts/python.exe`; pytest enabled with `args=["v2/tests"]`; analysis extraPaths `["v2/src"]`. |
| [`v2/tests/conftest.py`](../tests/conftest.py) | `_reset_env` autouse fixture stripping `AZURE_*` / `CWYD_*` / `LOAD_*` env vars between tests. |

### 10.2 Phase 1 — Infrastructure (✅ done; 3 P1 polish tweaks pending — §3.6.2)

| File | Purpose |
|---|---|
| [`v2/infra/main.bicep`](../infra/main.bicep) | Entry-point template. AVM-first (~95% coverage). UAMI + RBAC end-to-end (no Key Vault). Single `databaseType` param selects chat-history + vector-index in lockstep. 4 WAF flags drive cost/posture without branching topology. |
| [`v2/infra/main.parameters.json`](../infra/main.parameters.json) | Default parameter file (cosmosdb mode). |
| [`v2/infra/main.waf.parameters.json`](../infra/main.waf.parameters.json) | WAF-aligned parameter file (all 4 flags on). |
| [`v2/infra/abbreviations.json`](../infra/abbreviations.json) | Resource type → abbreviation map for naming. |
| [`v2/infra/modules/ai-project.bicep`](../infra/modules/ai-project.bicep) | Foundry Project (child of AI Services account; AVM lacks coverage). |
| [`v2/infra/modules/ai-project-search-connection.bicep`](../infra/modules/ai-project-search-connection.bicep) | Foundry Project ↔ AI Search connection (cosmosdb mode only). |
| [`v2/infra/modules/virtualNetwork.bicep`](../infra/modules/virtualNetwork.bicep) | Opinionated VNet wrapper (private-networking mode only). |
| [`v2/azure.yaml`](../azure.yaml) | azd manifest with v2 service paths. |
| [`v2/docker/`](../docker/) | Dockerfiles + docker-compose dev stack (backend-only / frontend-only profiles). |
| [`v2/scripts/`](../scripts/) | post-provision hooks (`.sh`, `.ps1`, `.py`). |
| [`v2/docs/infrastructure.md`](infrastructure.md) | Operator guide for the v2 substrate (resource topology, SKU table per WAF flag, troubleshooting). |

### 10.3 Phase 2 prerequisite — Registry primitive (✅ done; 11/11 tests)

| File | Purpose |
|---|---|
| [`v2/src/shared/registry.py`](../src/shared/registry.py) | Generic `Registry[T]` class. Case-insensitive keys, idempotent re-register, `KeyError` listing available providers. Methods: `register("key")` decorator, `get(key)`, `keys()`, `__contains__`, `__len__`. Underpins every provider domain in §3.5. |
| [`v2/tests/shared/test_registry.py`](../tests/shared/test_registry.py) | 11 tests covering registration, lookup, case-insensitivity, double-register rejection, empty domain/key validation, sorted keys. |

### 10.4 Documentation (✅ live)

| File | Purpose |
|---|---|
| [`v2/docs/development_plan.md`](development_plan.md) | This file. Source of truth for **what** to build and **when**. |
| [`v2/docs/pillars_of_development.md`](pillars_of_development.md) | Read-only product policy (Stable Core / Scenario Pack / Configuration Layer / Customization Layer). Never edited by agents. |
| [`v2/docs/infrastructure.md`](infrastructure.md) | Phase 1 infra design + operator guide. |
| [`v2/docs/plan/`](plan/) | Modernization plan, MVP, business-case docs (background reading). |

### 10.5 Agent guidance (✅ live; gate per Hard Rule #0)

| File | Purpose |
|---|---|
| [`.github/copilot-instructions.md`](../../.github/copilot-instructions.md) | Repo-wide always-loaded rules. Hard Rule #0 (sync agent guidance first), #4 (registry-first plug-and-play), #7 (banned tech + removed features incl. one-click). |
| [`.github/instructions/v2-workflow.instructions.md`](../../.github/instructions/v2-workflow.instructions.md) | "Step 0" gate; per-turn loop; banned/removed/forbidden split. |
| [`.github/instructions/v2-shared.instructions.md`](../../.github/instructions/v2-shared.instructions.md) | `applyTo: v2/src/{shared,providers,pipelines}/**`. Pluggability contract code template. |
| [`.github/instructions/v2-backend.instructions.md`](../../.github/instructions/v2-backend.instructions.md) | FastAPI conventions; routers consume `providers/<domain>/` via DI. |
| [`.github/instructions/v2-functions.instructions.md`](../../.github/instructions/v2-functions.instructions.md) | Blueprints invoke `pipelines/ingestion.py`; no parse/embed code in blueprints. |
| [`.github/instructions/v2-frontend.instructions.md`](../../.github/instructions/v2-frontend.instructions.md) | React/Vite conventions; consumes generated OpenAPI client. |
| [`.github/instructions/v2-infra.instructions.md`](../../.github/instructions/v2-infra.instructions.md) | Bicep + AVM conventions; matches §3.6 extensibility rules. |
| [`.github/instructions/v2-tests.instructions.md`](../../.github/instructions/v2-tests.instructions.md) | `tests/` mirrors `src/`; pytest + pytest-asyncio; `httpx.AsyncClient` for backend. |
