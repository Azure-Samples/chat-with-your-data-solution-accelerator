# v2 Environment Variables — Canonical Reference

**Pillar:** Configuration Layer
**Cleanup audit batch 2 / CU-012a**
**Last updated:** 2026-05-05

This is the operator-grade map between the three sources of truth for v2 runtime config:

1. **[v2/.env.sample](../.env.sample)** — what an operator copies to `v2/.env` (gitignored) for local dev.
2. **[v2/src/backend/core/settings.py](../src/backend/core/settings.py)** — the typed `AppSettings` (Pydantic v2 + pydantic-settings) that every backend / function / pipeline reads.
3. **[v2/infra/main.bicep](../infra/main.bicep)** outputs — what `azd up` injects into the Container App + Function App env-vars.

If a variable name appears in `.env.sample` but not in `AppSettings`, **pydantic-settings silently ignores it** (every sub-model uses `extra="ignore"`). Always cross-check spelling against the table below.

---

## Hard rules

* **No Key Vault.** Every credential is acquired at runtime via Managed Identity through the `providers/credentials/` registry domain. There are zero secret-shaped fields in `AppSettings` and zero `*_KEY` / `*_SECRET` / `*_PASSWORD` env vars.
* **No agent IDs in env.** `AZURE_AI_AGENT_ID` was removed in **CU-009 (2026-05-05, ADR 0008)**. The Foundry agent identity is bootstrapped lazily on first request and persisted in the application database. See [agents.md](agents.md) (CU-012b).
* **No bare LOG_LEVEL.** AppSettings reads `AZURE_LOG_LEVEL` (env_prefix `AZURE_`); the v1-style bare `LOG_LEVEL` is silently ignored.
* **No `APPLICATIONINSIGHTS_CONNECTION_STRING`.** AppSettings reads `AZURE_APP_INSIGHTS_CONNECTION_STRING` only (env_prefix `AZURE_`). The legacy bare name was dropped in CU-002b.
* **No v1 namespace.** Variables prefixed `MANAGED_IDENTITY_*`, `AZURE_OPENAI_RESOURCE`, `AZURE_AUTH_TYPE`, `CONVERSATION_FLOW`, `ORCHESTRATION_STRATEGY`, `USE_KEY_VAULT`, `APP_ENV`, `PROMPT_FLOW_*`, `OPEN_AI_FUNCTIONS_SYSTEM_PROMPT`, `SEMANTIC_KERNEL_SYSTEM_PROMPT`, every `AZURE_SEARCH_*_COLUMN`, `AZURE_SEARCH_FIELDS_*`, etc. are **gone**. See the v1 → v2 cross-reference at the bottom.

---

## v2 variables (canonical)

Every row corresponds to exactly one field in [`AppSettings`](../src/backend/core/settings.py) (or its sub-models) and one output in [`main.bicep`](../infra/main.bicep). Required / optional refers to **runtime requirement when the corresponding feature is exercised**; the local dev compose stack hard-codes defaults so most are optional out of the box.

### Identity (`IdentitySettings`, env_prefix `AZURE_`)

| Env var | Type | Req | AppSettings field | Bicep output | Default | Notes |
|---|---|---|---|---|---|---|
| `AZURE_TENANT_ID` | str | optional | `identity.tenant_id` | `AZURE_TENANT_ID` | `""` | Falls back to `AzureCliCredential` when empty. |
| `AZURE_UAMI_CLIENT_ID` | str | required (prod) | `identity.uami_client_id` | `AZURE_UAMI_CLIENT_ID` | `""` | UAMI clientId; required for `ManagedIdentityCredential` in Container Apps. |
| `AZURE_UAMI_PRINCIPAL_ID` | str | optional | `identity.uami_principal_id` | `AZURE_UAMI_PRINCIPAL_ID` | `""` | Used by post-provision RBAC seed. |
| `AZURE_UAMI_RESOURCE_ID` | str | optional | `identity.uami_resource_id` | `AZURE_UAMI_RESOURCE_ID` | `""` | Used by Container App `userAssignedIdentities`. |

### Foundry / AI Services (`FoundrySettings`, env_prefix `AZURE_AI_`)

| Env var | Type | Req | AppSettings field | Bicep output | Default | Notes |
|---|---|---|---|---|---|---|
| `AZURE_AI_PROJECT_ENDPOINT` | str | required | `foundry.project_endpoint` | `AZURE_AI_PROJECT_ENDPOINT` | `""` | Foundry IQ project; both orchestrators use it. |
| `AZURE_AI_SERVICES_ENDPOINT` | str | optional | `foundry.services_endpoint` | `AZURE_AI_SERVICES_ENDPOINT` | `""` | AI Services account hosting the project. |
| `AZURE_AI_SERVICE_LOCATION` | str | optional | `foundry.service_location` | `AZURE_AI_SERVICE_LOCATION` | `""` | Region of the AI Services account. |
| `AZURE_AI_AGENT_API_VERSION` | str | optional | `foundry.agent_api_version` | `AZURE_AI_AGENT_API_VERSION` | `""` | API version pinned by Bicep. |

### OpenAI deployments (`OpenAISettings`, env_prefix `AZURE_OPENAI_`)

| Env var | Type | Req | AppSettings field | Bicep output | Default | Notes |
|---|---|---|---|---|---|---|
| `AZURE_OPENAI_API_VERSION` | str | optional | `openai.api_version` | `AZURE_OPENAI_API_VERSION` | `""` | |
| `AZURE_OPENAI_GPT_DEPLOYMENT` | str | required | `openai.gpt_deployment` | `AZURE_OPENAI_GPT_DEPLOYMENT` | `""` | Primary chat deployment. |
| `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` | str | required (RAG) | `openai.embedding_deployment` | `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` | `""` | Used by ingestion + search providers. |
| `AZURE_OPENAI_TEMPERATURE` | float | optional | `openai.temperature` | — | `0.0` | Operator override only; not a Bicep output. |
| `AZURE_OPENAI_MAX_TOKENS` | int | optional | `openai.max_tokens` | — | `1000` | |

### Database (`DatabaseSettings`, env_prefix `AZURE_`)

The `db_type` switch determines which side of the table is required.

| Env var | Type | Req | AppSettings field | Bicep output | Default | Notes |
|---|---|---|---|---|---|---|
| `AZURE_DB_TYPE` | `cosmosdb` \| `postgresql` | required | `database.db_type` | `AZURE_DB_TYPE` | `cosmosdb` | Registry key for `databases.create(...)`. |
| `AZURE_INDEX_STORE` | `AzureSearch` \| `pgvector` | required | `database.index_store` | `AZURE_INDEX_STORE` | `AzureSearch` | Registry key for `search.create(...)`. Validator enforces `AzureSearch` ↔ `cosmosdb` and `pgvector` ↔ `postgresql`. **Known limitation (`B2-INGEST-PGVECTOR`, dev_plan §0.1):** the Functions ingest blueprints `batch_push` and `add_url` currently hard-code an Azure-Search `SearchClient` and do **not** dispatch through the search registry — so setting `AZURE_INDEX_STORE=pgvector` makes the chat-side search work but leaves the Functions ingest path broken. Cosmos+AzureSearch is the only fully-wired combination for ingestion today. |
| `AZURE_COSMOS_ENDPOINT` | str | required (cosmosdb) | `database.cosmos_endpoint` | `AZURE_COSMOS_ENDPOINT` | `""` | Required when `db_type=cosmosdb`. |
| `AZURE_COSMOS_ACCOUNT_NAME` | str | optional | `database.cosmos_account_name` | `AZURE_COSMOS_ACCOUNT_NAME` | `""` | |
| `AZURE_COSMOS_DATABASE_NAME` | str | optional | `database.cosmos_database_name` | — | `cwyd` | Operator override; not a Bicep output (constant). |
| `AZURE_COSMOS_CONTAINER_NAME` | str | optional | `database.cosmos_container_name` | — | `conversations` | Operator override; not a Bicep output (constant). |
| `AZURE_POSTGRES_ENDPOINT` | str | required (postgresql) | `database.postgres_endpoint` | `AZURE_POSTGRES_ENDPOINT` | `""` | Full libpq URI; required when `db_type=postgresql`. |
| `AZURE_POSTGRES_HOST` | str | optional | `database.postgres_host` | `AZURE_POSTGRES_HOST` | `""` | FQDN only (no port). |
| `AZURE_POSTGRES_NAME` | str | optional | `database.postgres_name` | `AZURE_POSTGRES_NAME` | `""` | Resource name. |
| `AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME` | str | optional | `database.postgres_admin_principal_name` | `AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME` | `""` | Used by post-provision Entra-token connection. |

### Search (`SearchSettings`, env_prefix `AZURE_AI_SEARCH_`)

Cosmosdb-mode only; ignored in pgvector-mode (where the search provider lives in Postgres).

| Env var | Type | Req | AppSettings field | Bicep output | Default | Notes |
|---|---|---|---|---|---|---|
| `AZURE_AI_SEARCH_ENDPOINT` | str | required (cosmosdb) | `search.endpoint` | `AZURE_AI_SEARCH_ENDPOINT` | `""` | |
| `AZURE_AI_SEARCH_NAME` | str | optional | `search.name` | `AZURE_AI_SEARCH_NAME` | `""` | |
| `AZURE_AI_SEARCH_INDEX` | str | optional | `search.index` | — | `cwyd-index` | Operator override; not a Bicep output. |
| `AZURE_AI_SEARCH_USE_SEMANTIC_SEARCH` | bool | optional | `search.use_semantic_search` | — | `true` | |
| `AZURE_AI_SEARCH_TOP_K` | int | optional | `search.top_k` | — | `5` | |

### Storage (`StorageSettings`, env_prefix `AZURE_`)

| Env var | Type | Req | AppSettings field | Bicep output | Default | Notes |
|---|---|---|---|---|---|---|
| `AZURE_STORAGE_ACCOUNT_NAME` | str | required (RAG) | `storage.storage_account_name` | `AZURE_STORAGE_ACCOUNT_NAME` | `""` | |
| `AZURE_STORAGE_BLOB_ENDPOINT` | str | required (RAG) | `storage.storage_blob_endpoint` | `AZURE_STORAGE_BLOB_ENDPOINT` | `""` | Primary blob URL. |
| `AZURE_DOCUMENTS_CONTAINER` | str | required (RAG) | `storage.documents_container` | `AZURE_DOCUMENTS_CONTAINER` | `""` | Source container for ingestion. |
| `AZURE_DOC_PROCESSING_QUEUE` | str | required (RAG) | `storage.doc_processing_queue` | `AZURE_DOC_PROCESSING_QUEUE` | `""` | Storage queue consumed by `batch_push`. See `AZURE_INDEX_STORE` note — `batch_push` writes through a hard-coded Azure-Search `SearchClient` regardless of `index_store` (`B2-INGEST-PGVECTOR`). |

### Observability (`ObservabilitySettings`, env_prefix `AZURE_`)

| Env var | Type | Req | AppSettings field | Bicep output | Default | Notes |
|---|---|---|---|---|---|---|
| `AZURE_LOG_LEVEL` | str | optional | `observability.log_level` | — | `INFO` | Bare `LOG_LEVEL` is **ignored**. |
| `AZURE_APP_INSIGHTS_CONNECTION_STRING` | str | optional | `observability.app_insights_connection_string` | `AZURE_APP_INSIGHTS_CONNECTION_STRING` | `""` | When non-empty, `azure-monitor-opentelemetry` exports to App Insights. Bare `APPLICATIONINSIGHTS_CONNECTION_STRING` is **not** honored (CU-002b). |

### Network (`NetworkSettings`, env_prefix `AZURE_`)

| Env var | Type | Req | AppSettings field | Bicep output | Default | Notes |
|---|---|---|---|---|---|---|
| `AZURE_BACKEND_URL` | str | optional | `network.backend_url` | `AZURE_BACKEND_URL` | `""` | |
| `AZURE_FRONTEND_URL` | str | optional | `network.frontend_url` | `AZURE_FRONTEND_URL` | `""` | Backend CORS must allow this. |
| `AZURE_FUNCTION_APP_URL` | str | optional | `network.function_app_url` | `AZURE_FUNCTION_APP_URL` | `""` | |
| `AZURE_FUNCTION_APP_NAME` | str | optional | `network.function_app_name` | `AZURE_FUNCTION_APP_NAME` | `""` | Used by `azd deploy func`. |
| `AZURE_VNET_NAME` | str | optional | `network.vnet_name` | `AZURE_VNET_NAME` | `""` | Empty when `enablePrivateNetworking=false`. |
| `AZURE_VNET_RESOURCE_ID` | str | optional | `network.vnet_resource_id` | `AZURE_VNET_RESOURCE_ID` | `""` | Empty when `enablePrivateNetworking=false`. |
| `AZURE_BASTION_NAME` | str | optional | `network.bastion_name` | `AZURE_BASTION_NAME` | `""` | Empty when `enablePrivateNetworking=false`. |
| `BACKEND_CORS_ORIGINS` | str (CSV or JSON) | optional | `network.cors_origins` | — | `[]` | **Bare** name (no `AZURE_` prefix); `AliasChoices("BACKEND_CORS_ORIGINS", "cors_origins")`. Accepts CSV (`a,b`), JSON (`["a","b"]`), or list. |

### Orchestrator (`OrchestratorSettings`, env_prefix `CWYD_ORCHESTRATOR_`)

Distinct namespace because the orchestrator is **runtime-tunable**, not infra-pinned.

| Env var | Type | Req | AppSettings field | Bicep output | Default | Notes |
|---|---|---|---|---|---|---|
| `CWYD_ORCHESTRATOR_NAME` | `langgraph` \| `agent_framework` | optional | `orchestrator.name` | — | `langgraph` | Registry key passed to `orchestrators.create(...)`. **Naming caveat (`B1-MAF-MISLABEL`, dev_plan §0.1):** the value `agent_framework` is the *registry key*, not the OSS `agent-framework` PyPI package. The orchestrator behind that key today wraps the `azure.ai.agents` SDK (Foundry hosted-agents). The swap to the real OSS `agent_framework` / `agent-framework-foundry` packages is Phase B-IMPL work and will preserve the key. |

### Speech (`SpeechSettings`, env_prefix `AZURE_SPEECH_`)

Wires `GET /api/speech` (`v2/src/backend/routers/speech.py`) which mints a 10-minute AAD-bearer Speech authorization token for the browser SDK. Hard Rule #2 — UAMI must hold **Cognitive Services Speech User** (`f2dc8367-1007-4938-bd23-fe263f013447`) on the `spch-*` account; no subscription keys.

| Env var | Type | Req | AppSettings field | Bicep output | Default | Notes |
|---|---|---|---|---|---|---|
| `AZURE_SPEECH_SERVICE_NAME` | str | optional | `speech.service_name` | `AZURE_SPEECH_SERVICE_NAME` | `""` | Diagnostics only; STS endpoint is region-derived. |
| `AZURE_SPEECH_SERVICE_REGION` | str | required for `/api/speech` | `speech.service_region` | `AZURE_SPEECH_SERVICE_REGION` | `""` | Empty → router returns **503 Speech service not configured**. |
| `AZURE_SPEECH_ACCOUNT_RESOURCE_ID` | str | required | `speech.account_resource_id` | `AZURE_SPEECH_ACCOUNT_RESOURCE_ID` | `""` | Sent as `x-ms-cognitiveservices-resource-id` header on the AAD-bearer STS issueToken POST. |
| `AZURE_SPEECH_RECOGNIZER_LANGUAGES` | CSV str | optional | `speech.recognizer_languages` | — | `"en-US,fr-FR,de-DE,it-IT"` | Comma-split client-side; passed to `AutoDetectSourceLanguageConfig.fromLanguages(...)`. |

### Content Safety (`ContentSafetySettings`, env_prefix `AZURE_CONTENT_SAFETY_`)

Wires the prompt-shielding guard injected into `run_chat(...)` via `Depends(get_content_safety_guard)`. The guard calls `AnalyzeText` on a standalone Cognitive Services account of kind `ContentSafety` (deployed by the inline `cogContentSafety` module in `v2/infra/main.bicep`). Hard Rule #2 — UAMI must hold **Cognitive Services User** (`a97b65f3-24c7-4388-baec-2e87135dc908`) on the `cs-*` account; no subscription keys. The Bicep deploys the account unconditionally and pins `AZURE_CONTENT_SAFETY_ENABLED='true'` on the backend container app at infra level; operators flip the guard OFF per-request via the admin runtime override `PATCH /api/admin/config {"content_safety_enabled": false}` (`RuntimeConfig.content_safety_enabled` `False` short-circuits to `None` even when the lifespan client is present — operator-off wins over env baseline).

| Env var | Type | Req | AppSettings field | Bicep output | Default | Notes |
|---|---|---|---|---|---|---|
| `AZURE_CONTENT_SAFETY_ENDPOINT` | str | required for guard | `content_safety.endpoint` | `AZURE_CONTENT_SAFETY_ENDPOINT` | `""` | Regional Cognitive Services endpoint (e.g. `https://cs-cwyd001.cognitiveservices.azure.com/`). Empty → lifespan leaves `app.state.content_safety_client = None`; pipeline runs unguarded. |
| `AZURE_CONTENT_SAFETY_ENABLED` | bool | required for guard | `content_safety.enabled` | (`'true'` literal on backend container-app `env`) | `False` | Operator opt-in. Both `enabled=true` AND a non-empty endpoint are required at lifespan to build the client; either alone is treated as "off" (no exception raised). |
| `AZURE_CONTENT_SAFETY_SEVERITY_THRESHOLD` | int 0-7 | optional | `content_safety.severity_threshold` | — | `4` | Inclusive lower bound at which verdicts trip. Azure reports 0/2/4/6; default `4` matches v1 `enable_content_safety: true` behavior. Validation ceiling `7` lets operators set the guard effectively-off without rejection at settings load. |

### Root (`AppSettings`, env_prefix `AZURE_`)

| Env var | Type | Req | AppSettings field | Bicep output | Default | Notes |
|---|---|---|---|---|---|---|
| `AZURE_SOLUTION_SUFFIX` | str | optional | `solution_suffix` | `AZURE_SOLUTION_SUFFIX` | `""` | |
| `AZURE_RESOURCE_GROUP` | str | optional | `resource_group` | `AZURE_RESOURCE_GROUP` | `""` | |
| `AZURE_LOCATION` | str | optional | `location` | `AZURE_LOCATION` | `""` | |
| `AZURE_AI_SERVICE_LOCATION` | str | optional | `ai_service_location` | `AZURE_AI_SERVICE_LOCATION` | `""` | Mirrored at root + on `FoundrySettings`. |
| `AZURE_ENVIRONMENT` | `local` \| `production` | optional | `environment` | (set by Bicep on Container App) | `local` | Stable Core code branches on this — never `os.getenv` ad-hoc. |

### Frontend (build-time, not consumed by AppSettings)

| Env var | Type | Req | Consumer | Default | Notes |
|---|---|---|---|---|---|
| `VITE_BACKEND_URL` | str | required | Vite build | `http://localhost:8000` | Baked into the SPA at build time. |

---

## Removed in v2 (do not re-add)

| Variable | Reason | Removed in |
|---|---|---|
| `AZURE_AI_AGENT_ID` | Foundry agent identity moved to lazy DB-backed bootstrap; see [agents.md](agents.md). | CU-009 (2026-05-05, ADR 0008) |
| `LOG_LEVEL` (bare) | Replaced by `AZURE_LOG_LEVEL` (env_prefix `AZURE_`). | CU-002b |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` (bare) | Replaced by `AZURE_APP_INSIGHTS_CONNECTION_STRING` (env_prefix `AZURE_`). | CU-002b |
| `USE_KEY_VAULT`, all `*_KEY` / `*_SECRET` reads | No Key Vault in v2 — Managed Identity only (Hard Rule #7). | Phase 1 |
| `MANAGED_IDENTITY_CLIENT_ID`, `MANAGED_IDENTITY_RESOURCE_ID` | Replaced by `AZURE_UAMI_CLIENT_ID` / `AZURE_UAMI_RESOURCE_ID`. | Phase 2 |
| `AZURE_OPENAI_RESOURCE` | Collapsed into `AZURE_AI_SERVICES_ENDPOINT` / `AZURE_AI_PROJECT_ENDPOINT`. | Phase 2 |
| `AZURE_AUTH_TYPE` | Always RBAC + Managed Identity in v2. | Phase 1 |
| `ORCHESTRATION_STRATEGY` | Banned — replaced by `CWYD_ORCHESTRATOR_NAME` (registry key). | Hard Rule #7 |
| `CONVERSATION_FLOW` | Banned (Prompt Flow removed). | Hard Rule #7 |
| `PROMPT_FLOW_ENDPOINT_NAME`, `PROMPT_FLOW_DEPLOYMENT_NAME` | Banned (Prompt Flow removed). | Hard Rule #7 |
| `AZURE_OPENAI_SYSTEM_MESSAGE`, `OPEN_AI_FUNCTIONS_SYSTEM_PROMPT`, `SEMANTIC_KERNEL_SYSTEM_PROMPT` | System prompts moved to `backend/core/agents/definitions.py` (`AgentDefinition.instructions`); see [agents.md](agents.md). | Phase 3 |
| `AZURE_SEARCH_FIELDS_*`, `AZURE_SEARCH_*_COLUMN` (23 vars) | Index schema is fixed in v2 (`backend/core/providers/search/_schema.py`). | Phase 3 |
| `AZURE_SEARCH_INDEX_IS_PRECHUNKED`, `AZURE_SEARCH_INDEXER_NAME`, `AZURE_SEARCH_DATASOURCE_NAME`, `AZURE_SEARCH_DOC_UPLOAD_BATCH_SIZE`, `AZURE_SEARCH_CONVERSATIONS_LOG_INDEX`, `AZURE_SEARCH_FILTER`, `AZURE_SEARCH_ENABLE_IN_DOMAIN`, `AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG` | Replaced by Foundry IQ knowledge stores + the typed `SearchSettings`. | Phase 3 |
| `AZURE_OPENAI_MODEL`, `AZURE_OPENAI_MODEL_NAME`, `AZURE_OPENAI_VISION_MODEL`, `AZURE_OPENAI_TOP_P`, `AZURE_OPENAI_STOP_SEQUENCE`, `AZURE_OPENAI_STREAM`, `AZURE_OPENAI_EMBEDDING_MODEL` | Replaced by `AZURE_OPENAI_GPT_DEPLOYMENT` / `_EMBEDDING_DEPLOYMENT` (deployment names, not model names). | Phase 2 |
| `AZURE_COMPUTER_VISION_*`, `AZURE_FORM_RECOGNIZER_ENDPOINT` | Replaced by Foundry Document Intelligence + Vision via the Foundry account. | Phase 4 |
| `AZURE_ML_WORKSPACE_NAME` | No standalone ML workspace in v2. | Phase 1 |
| `AZURE_BLOB_ACCOUNT_NAME`, `AZURE_BLOB_CONTAINER_NAME`, `AZURE_STORAGE_ACCOUNT_ENDPOINT`, `AzureWebJobsStorage`, `DOCUMENT_PROCESSING_QUEUE_NAME` | Replaced by typed `StorageSettings` (`AZURE_STORAGE_*`, `AZURE_DOCUMENTS_CONTAINER`, `AZURE_DOC_PROCESSING_QUEUE`). | Phase 4 |
| `AZURE_COSMOSDB_DATABASE`, `AZURE_COSMOSDB_ACCOUNT`, `AZURE_COSMOSDB_CONVERSATIONS_CONTAINER`, `AZURE_COSMOSDB_ENABLE_FEEDBACK` | Replaced by typed `DatabaseSettings` (`AZURE_COSMOS_*`). | Phase 2 |
| `AZURE_POSTGRESQL_USER`, `AZURE_POSTGRESQL_DATABASE_NAME`, `AZURE_POSTGRESQL_HOST_NAME` | Replaced by `AZURE_POSTGRES_ENDPOINT` (full libpq URI) + `AZURE_POSTGRES_HOST` / `_NAME`. | Phase 2 |
| `APP_ENV` | Replaced by `AZURE_ENVIRONMENT` (`local` \| `production`). | Phase 2 |
| `BACKEND_URL` (read by v1 frontend) | Replaced by `VITE_BACKEND_URL` (build-time) + `AZURE_BACKEND_URL` (runtime). | Phase 1 |
| `AZURE_SUBSCRIPTION_ID` | Not consumed by v2 runtime (azd reads it from the CLI context). | Phase 1 |

---

## v1 → v2 cross-reference (selected)

Use this when porting an existing v1 `.env` over to v2 (or when scanning v1 docs that reference an old name).

| v1 var | v2 equivalent | Notes |
|---|---|---|
| `MANAGED_IDENTITY_CLIENT_ID` | `AZURE_UAMI_CLIENT_ID` | Renamed to align with Bicep `userAssignedIdentity` module. |
| `MANAGED_IDENTITY_RESOURCE_ID` | `AZURE_UAMI_RESOURCE_ID` | Same. |
| `AZURE_OPENAI_RESOURCE` + `AZURE_OPENAI_API_VERSION` | `AZURE_AI_PROJECT_ENDPOINT` + `AZURE_OPENAI_API_VERSION` | Resource name collapsed into the Foundry project endpoint. |
| `AZURE_OPENAI_MODEL` / `AZURE_OPENAI_MODEL_NAME` | `AZURE_OPENAI_GPT_DEPLOYMENT` | v2 names the deployment, not the model. |
| `AZURE_OPENAI_EMBEDDING_MODEL` | `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` | Same. |
| `AZURE_COSMOSDB_ACCOUNT` | `AZURE_COSMOS_ACCOUNT_NAME` | Underscore normalization. |
| `AZURE_COSMOSDB_DATABASE` | `AZURE_COSMOS_DATABASE_NAME` | Same. |
| `AZURE_COSMOSDB_CONVERSATIONS_CONTAINER` | `AZURE_COSMOS_CONTAINER_NAME` | Same. |
| `AZURE_POSTGRESQL_HOST_NAME` | `AZURE_POSTGRES_HOST` | Underscore normalization. |
| `AZURE_POSTGRESQL_USER` | (removed) | Workload supplies an Entra token; user comes from `AZURE_UAMI_CLIENT_ID`. |
| `DATABASE_TYPE` | `AZURE_DB_TYPE` | Prefixed under env_prefix `AZURE_`. |
| `LOG_LEVEL` | `AZURE_LOG_LEVEL` | Prefix added; bare name is silently ignored. |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | `AZURE_APP_INSIGHTS_CONNECTION_STRING` | Prefix added; bare name is silently ignored. |
| `BACKEND_URL` | `VITE_BACKEND_URL` (frontend build) + `AZURE_BACKEND_URL` (runtime) | Split into build-time vs. runtime concerns. |
| `ORCHESTRATION_STRATEGY` | `CWYD_ORCHESTRATOR_NAME` | Banned name; new namespace + new value set (`langgraph` \| `agent_framework`). |
| `CONVERSATION_FLOW` | (removed) | Prompt Flow banned (Hard Rule #7). |
| `AZURE_AI_AGENT_ID` | (removed) | Lazy DB-backed bootstrap; see [agents.md](agents.md). |

---

## Acceptance gates (CU-012a)

* `grep -r 'AZURE_AI_AGENT_ID' v2/` returns only deprecation-notice hits (this file + cleanup_audit.md).
* Every variable in [v2/.env.sample](../.env.sample) appears in exactly one row of the v2-variables tables above (or in the frontend table) and resolves to a real `AppSettings` field path.
* Every Bicep output declared in [v2/infra/main.bicep](../infra/main.bicep) (`grep -E '^output AZURE_'`) appears in the **Bicep output** column of exactly one row.
