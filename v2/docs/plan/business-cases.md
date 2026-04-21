# CWYD v2 — Business Cases: v1 → v2 Carryover

This document maps every business case, scenario, and capability in CWYD v1 to its v2 equivalent — what's kept, what changes, and what's deferred.

---

## 1. Industry Scenarios

CWYD v1 ships with three documented industry scenarios, each with sample data and recommended configuration. All three carry to v2.

### 1.1 Employee Onboarding & Benefits Assistant

| | v1 | v2 |
|---|---|---|
| **Use Case** | New employees researching health/retirement benefits, handbooks, corporate policies | Same |
| **Sample Data** | `data/employee_handbook.pdf`, `data/Benefit_Options.pdf`, `data/Northwind_Health_Plus_Benefits_Details.pdf`, `data/Northwind_Standard_Benefits_Details.pdf`, `data/PerksPlus.pdf`, `data/Woodgrove_Insurance_Summary_Plan_Description_Employee_Benefits.pdf` | Same files, loaded via post-deploy script |
| **Orchestrator** | Semantic Kernel (recommended) | LangGraph or Agent Framework |
| **Database** | CosmosDB | CosmosDB or PostgreSQL |
| **Conversation Flow** | BYOD | BYOD or Custom |
| **Preset** | `employee assistant` in active.json | Same — `active.json` preset carried over |
| **v2 Phase** | M3 (core chat with sample data) |

### 1.2 Contract Review & Legal Assistance

| | v1 | v2 |
|---|---|---|
| **Use Case** | Legal/compliance/finance professionals reviewing, summarizing, and comparing contracts | Same |
| **Sample Data** | `data/contract_data/` folder with sample legal contracts | Same files, loaded via post-deploy script |
| **Orchestrator** | Semantic Kernel (recommended) | LangGraph or Agent Framework |
| **Database** | CosmosDB | CosmosDB or PostgreSQL |
| **Conversation Flow** | BYOD | BYOD or Custom |
| **Preset** | `contract assistant` in active.json | Same — `active.json` preset carried over |
| **System Prompt** | Contract-focused: "You are a contract assistant…" | Same — configurable via `active.json` |
| **v2 Phase** | M3 (core chat with sample data) |

### 1.3 Financial Advisor (Fund Research)

| | v1 | v2 |
|---|---|---|
| **Use Case** | Financial advisors preparing for client meetings — reviewing funds, risks, performance | Same |
| **Sample Data** | `data/Woodgrove - Cyber Risk Insurance Policy_Commercial Insurance.pdf`, `data/Woodgrove - Insurance Underwriting_Key Prompts for Underwriters.pdf`, `data/Woodgrove Asset Management - Prospective of Asset Management Funds.pdf`, `data/MSFT_FY23Q4_10K.docx`, `data/PressReleaseFY23Q4.docx` | Same files |
| **Orchestrator** | Any (OpenAI Functions recommended) | LangGraph or Agent Framework |
| **Database** | CosmosDB or PostgreSQL | Same |
| **Preset** | `default` in active.json | Same |
| **v2 Phase** | M3 |

### 1.4 Assistant Presets Summary

| Preset | Description | v1 → v2 |
|---|---|---|
| `default` | General-purpose assistant | **Kept** — `active.json` |
| `contract assistant` | Legal/contract-focused prompts | **Kept** — `active.json` |
| `employee assistant` | HR/benefits-focused prompts | **Kept** — `active.json` |

All presets are runtime-switchable via `active.json` → `ai_assistant_type`. No redeployment needed.

---

## 2. Conversation Flows

| Flow | v1 | v2 | Status |
|---|---|---|---|
| **Custom** | Full-featured, all databases, all orchestrators, advanced image processing, semantic search | Same — now async-native via FastAPI | **Kept** |
| **BYOD** (On Your Data) | Delegates to Azure OpenAI's built-in RAG; CosmosDB only; simplified orchestration | Same constraint (CosmosDB only); routed through Foundry IQ instead of direct SDK | **Kept** |

### Feature Availability by Flow

| Feature | Custom | BYOD |
|---|---|---|
| PostgreSQL support | ✅ | ❌ (CosmosDB only) |
| CosmosDB support | ✅ | ✅ |
| All orchestrators | ✅ | ✅ |
| Advanced image processing | ✅ (CosmosDB only) | ❌ |
| Integrated vectorization | ✅ (CosmosDB only) | ✅ |
| Semantic search | ✅ | ✅ |
| Post-answering validation | ✅ | ❌ |
| Custom business logic | ✅ | ❌ |

---

## 3. Orchestration Strategy Mapping

| v1 Strategy | v2 Equivalent | Status | Notes |
|---|---|---|---|
| **OpenAI Functions** | **OpenAI Functions** (via Foundry IQ) | **Kept** | Updated to route through Foundry IQ (Knowledge Base, Embeddings) |
| **Semantic Kernel** | — | **Removed** | Consolidated into LangGraph + Agent Framework |
| **LangChain** | **LangGraph Agent** | **Upgraded** | `ZeroShotAgent` → `StateGraph` + `ToolNode` |
| **Prompt Flow** | — | **Removed** | Experimental; never reached production parity |
| *(new)* | **Azure AI Agent Framework** | **Added** | Agent lifecycle, tool management, tracing via Foundry IQ |

### Why 4 → 3?

v1 maintained four orchestrators with significant overlap and maintenance burden. v2 consolidates to three strategically distinct options:

| v2 Orchestrator | Best For |
|---|---|
| **OpenAI Functions** | Direct tool calling, simple RAG patterns, lowest latency |
| **LangGraph** | Multi-step reasoning, graph-based workflows, conditional branching |
| **Agent Framework** | Managed agent lifecycle, built-in tracing, Azure-native multi-agent (future) |

---

## 4. Database Backends

### 4.1 Feature Compatibility Matrix

| Feature | PostgreSQL | CosmosDB |
|---|---|---|
| Chat history | ✅ (async) | ✅ (async) |
| Vector search (pgvector / AI Search) | ✅ pgvector | ✅ Azure AI Search |
| BYOD conversation flow | ❌ | ✅ |
| Integrated vectorization | ❌ | ✅ |
| Advanced image processing | ❌ | ✅ |
| Custom conversation flow | ✅ | ✅ |
| All orchestrators | ✅ | ✅ |
| Semantic search | ✅ (via AI Search) | ✅ (via AI Search) |

### 4.2 What Changes in v2

| Aspect | v1 | v2 |
|---|---|---|
| **PostgreSQL orchestrator restriction** | SK recommended (only fully tested) | All 3 orchestrators supported |
| **Client libraries** | psycopg2 (sync) + asyncpg | asyncpg only (full async) |
| **CosmosDB client** | azure-cosmos (sync) | azure-cosmos (async) |
| **Schema creation** | `create_postgres_tables.py` post-deploy | Same — automated via post-deploy script |
| **Config** | Key Vault + env vars | Env vars only (RBAC + Managed Identity) |
| **Switching** | `DATABASE_TYPE` env var | Same — `databaseType` Bicep param + `DATABASE_TYPE` env var |

---

## 5. Data Ingestion

### 5.1 Push Model (Custom Chunking)

| | v1 | v2 |
|---|---|---|
| **Supported DBs** | Both | Both |
| **Architecture** | Monolithic Azure Functions | Split Functions: `batch_start`, `batch_push`, `add_url`, `search_skill` |
| **Trigger** | Blob upload → Event Grid → Queue → Function | Same event-driven pattern |
| **Chunking strategies** | Layout, Page, Fixed-Size Overlap, Paragraph | All 4 carried over |
| **URL indexing** | `add_url` function | Same — dedicated split function |
| **v2 Phase** | M6 (RAG Indexing Pipeline) |

### 5.2 Integrated Vectorization (Pull Model)

| | v1 | v2 |
|---|---|---|
| **Supported DBs** | CosmosDB only | CosmosDB only (same constraint) |
| **Architecture** | Azure AI Search pull-based indexers with built-in chunking + vectorization | Same |
| **Switching** | Deployment-time only — requires index deletion to change | Same |
| **Chunking** | AI-powered layout analysis (fixed) | Same |
| **v2 Phase** | M6 |

### 5.3 Chunking Strategies

| Strategy | Description | v1 → v2 |
|---|---|---|
| **Layout** | AI-driven chunking via Document Intelligence | **Kept** |
| **Page** | Break by document pages | **Kept** |
| **Fixed-Size Overlap** | Fixed chunks (e.g., 250 words) with 10–25% overlap | **Kept** |
| **Paragraph** | Break by paragraphs with summarization | **Kept** |

---

## 6. Advanced Features

| Feature | v1 Status | v2 Status | Phase | Notes |
|---|---|---|---|---|
| **Speech-to-Text** | Azure Speech Services; 4 default languages (en-US, fr-FR, de-DE, it-IT); configurable | **Kept** | M5 | Same SDK, same config pattern |
| **Advanced Image Processing** | GPT-4 Vision + Computer Vision; CosmosDB + Custom flow only | **Kept** | M6+ | Same constraints; may slip to post-MVP |
| **Chat History** | CosmosDB/PG storage; toggle via admin; audit trail | **Kept** — both DBs, async | M4 | Feature parity, now async |
| **Semantic Search** | Azure AI Search semantic ranking | **Kept** | M3 | Same config toggle |
| **Teams Extension** | Azure Bot Service + Teams Toolkit | **Deferred** | — | Focus v2 on core; extensibility built in for later |
| **Document Intelligence** | PDF/image table extraction, layout analysis, handwriting | **Kept** | M6 | Same Azure service |

### 6.1 Speech-to-Text Detail

| | v1 | v2 |
|---|---|---|
| **Default languages** | `en-US,fr-FR,de-DE,it-IT` | Same |
| **Config** | `AZURE_SPEECH_RECOGNIZER_LANGUAGES` env var | Same — Pydantic Settings |
| **Custom languages** | `azd env set AZURE_SPEECH_RECOGNIZER_LANGUAGES "en-US,es-ES,ja-JP"` | Same pattern |

### 6.2 Advanced Image Processing Detail

| | v1 | v2 |
|---|---|---|
| **Requires** | CosmosDB + Custom flow + integrated vectorization OFF | Same constraints |
| **Pipeline** | GPT-4 Vision captions → Computer Vision embeddings → hybrid search | Same |
| **Config** | `USE_ADVANCED_IMAGE_PROCESSING=true`, `ADVANCED_IMAGE_PROCESSING_MAX_IMAGES=1` | Same env vars → Pydantic Settings |
| **Supported types** | JPEG, JPG, PNG | Same |

---

## 7. Admin & Configuration

| Capability | v1 (Streamlit) | v2 (React) | Phase |
|---|---|---|---|
| **Document upload** | Streamlit "Ingest Data" page | React admin page | M5 |
| **Explore indexed data** | Streamlit "Explore Data" page | React admin page | M5 |
| **Prompt configuration** | Streamlit "Configuration" page + active.json | React admin page + active.json | M5 |
| **Assistant preset switching** | Streamlit dropdown (default, contract, employee) | React admin + active.json | M5 |
| **System prompt tuning** | Runtime via admin panel | Runtime via admin + active.json | M2 |
| **Model parameter tuning** | temperature, top_p, max_tokens via admin | Same — active.json + env vars | M2 |
| **Orchestrator switching** | `ORCHESTRATION_STRATEGY` env var | `ORCHESTRATOR` env var + active.json | M2 |
| **Chat history toggle** | Admin panel toggle | Admin panel toggle | M4 |
| **Search config** | top_k, semantic search toggle | Same — Pydantic Settings | M2 |

### Key Change: Streamlit → React

The admin UI moves from a separate Streamlit service (port 8501, separate auth, separate deployment) to integrated React pages in the main frontend. Benefits:
- Single deployment (one container)
- Shared authentication (Entra ID)
- Consistent UI (Fluent UI v9)
- No separate App Service resource

---

## 8. Enterprise & Security

| Feature | v1 | v2 | Status |
|---|---|---|---|
| **Microsoft Entra ID** | App Service built-in auth | FastAPI middleware + App Service auth | **Kept** — same capability |
| **Private networking** | VNet + Private Endpoints + Bastion (toggle) | Same — `enablePrivateNetworking` Bicep param | **Kept** |
| **Key Vault** | Stores `FUNCTION-KEY` and config secrets | **Removed** — RBAC + Managed Identity only | **Changed** (MACAE pattern) |
| **SSL/TLS** | Enabled (PostgreSQL `sslmode=verify-full`) | Same | **Kept** |
| **RBAC** | Partial (some API keys still used) | Full — no API keys, Managed Identity everywhere | **Improved** |
| **WAF: Monitoring** | `enableMonitoring` toggle → App Insights + Log Analytics | Same toggle | **Kept** |
| **WAF: Scalability** | `enableScalability` toggle → higher SKUs, autoscale | Same toggle | **Kept** |
| **WAF: Redundancy** | `enableRedundancy` toggle → zone-redundant, paired regions | Same toggle | **Kept** |
| **WAF: Purge Protection** | `enablePurgeProtection` for Key Vault | Kept (Key Vault deployed but empty) | **Kept** |
| **Deployment regions** | australiaeast, eastus2, japaneast, uksouth | Same initial set | **Kept** |

---

## 9. Supported File Types

All v1 file types carry to v2 unchanged:

| Type | Processing | v1 → v2 |
|---|---|---|
| PDF | Document Intelligence (layout, tables, handwriting) | **Kept** |
| DOCX | Document Intelligence | **Kept** |
| TXT | Direct text processing | **Kept** |
| MD | Markdown parsing | **Kept** |
| HTML | HTML parsing | **Kept** |
| JSON | Structured data extraction | **Kept** |
| JPEG / JPG / PNG | Advanced image processing (GPT-4 Vision + Computer Vision) | **Kept** |

---

## 10. Deployment Patterns

| Pattern | v1 | v2 | Status |
|---|---|---|---|
| **`azd up`** | Primary deployment path | Primary — only supported cloud deploy method | **Kept** |
| **One-click "Deploy to Azure"** | ARM template button in README | **Removed** — `azd`-only | **Removed** |
| **Docker Compose** | Local development orchestration | Same | **Kept** |
| **Container hosting** | App Service with container | Same | **Kept** |
| **Code-based hosting** | App Service code deploy (legacy) | Removed — container-only | **Removed** |

---

## 11. Summary Carryover Matrix

| Capability | v1 → v2 | Phase | Notes |
|---|---|---|---|
| Employee Onboarding scenario | **Kept** | M3 | New orchestrators |
| Contract Review scenario | **Kept** | M3 | New orchestrators |
| Financial Advisor scenario | **Kept** | M3 | New orchestrators |
| Custom conversation flow | **Kept** | M3 | Async-native |
| BYOD conversation flow | **Kept** | M3 | Via Foundry IQ |
| OpenAI Functions orchestrator | **Kept** | M3 | Via Foundry IQ |
| LangChain orchestrator | **Upgraded** → LangGraph | M3 | `StateGraph` + `ToolNode` |
| Semantic Kernel orchestrator | **Removed** | — | Consolidated |
| Prompt Flow orchestrator | **Removed** | — | Consolidated |
| Azure AI Agent Framework | **Added** | M4 | New |
| PostgreSQL backend | **Kept** | M4 | All orchestrators now |
| CosmosDB backend | **Kept** | M4 | Async client |
| Push ingestion pipeline | **Kept** | M6 | Split functions |
| Integrated vectorization | **Kept** | M6 | CosmosDB only |
| 4 chunking strategies | **Kept** | M6 | All carried over |
| Speech-to-Text | **Kept** | M5 | Same SDK |
| Advanced image processing | **Kept** | M6+ | CosmosDB + Custom only |
| Chat history | **Kept** | M4 | Both DBs, async |
| Semantic search | **Kept** | M3 | Same toggle |
| Document Intelligence | **Kept** | M6 | Same service |
| Teams extension | **Deferred** | — | Future version |
| Admin UI | **Changed** → React | M5 | From Streamlit |
| Entra ID auth | **Kept** | M5 | Middleware-based |
| Private networking | **Kept** | M1 | Bicep toggle |
| Key Vault secrets | **Removed** | M1 | RBAC + MI only |
| WAF toggles | **Kept** | M1 | All 4 toggles |
| `azd up` deploy | **Kept** | M1 | Only cloud method |
| One-click ARM deploy | **Removed** | — | `azd`-only |
| Docker Compose local | **Kept** | M1 | Same pattern |
| 7 file types | **Kept** | M6 | All carried over |
| Assistant presets (3) | **Kept** | M2 | `active.json` |

---

## Related Documents

| Document | Description |
|---|---|
| [development_plan.md](../development_plan.md) | Detailed task-level implementation plan (53 tasks, 7 phases) |
| [modernization-plan.md](modernization-plan.md) | Library upgrades, architecture changes, migration strategy |
| [mvp-release.md](mvp-release.md) | MVP scope, milestones (M1–M7), release criteria |
