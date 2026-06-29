<!-- markdownlint-disable-file -->
# CWYD v2 backend — environment variable diff (READS vs INFRA SETS)

Research-only. Goal: find ALL missing / misnamed env vars on the backend Container App after `azd up` — not just CORS.

- (X) what the backend READS: `v2/src/backend/core/settings.py` (every `BaseSettings` subclass) + any `os.environ`/`os.getenv` outside settings.
- (Y) what infra SETS: the backend Container App `env` array in `v2/infra/main.bicep` L1808–1912 (`backendContainerApp` module).

## TL;DR

- **No missing-AND-required var crashes the backend at boot.** Every settings field has a safe empty-string / typed default; the only boot-time validator (`DatabaseSettings._enforce_mode_consistency`) checks `AZURE_COSMOS_ENDPOINT` + `AZURE_INDEX_STORE`, both of which **are** set. `AppSettings()` constructs cleanly.
- **Every load-bearing var (Foundry, OpenAI deployments, Search endpoint, Cosmos/Postgres, Storage, identity, orchestrator, DB routing) is set in bicep AND read under the matching name.** The backend can reach all data stores. Step-5 cross-check below is all green.
- The "seems missing variables" symptom is driven by a small set of **missing-OPTIONAL** vars that silently fall back to dev/local defaults — chiefly **`BACKEND_CORS_ORIGINS`** (the one true alias subtlety) plus a cluster of **informational/admin-display** fields that read empty in the cloud and make `GET /api/admin/status` look half-configured.
- One **fragile-by-coincidence** var: **`AZURE_AI_SEARCH_INDEX`** is not set; it works only because the settings default `cwyd-index` happens to equal the provisioned index name.
- Two **set-but-unread** vars exist (harmless): `AZURE_OPENAI_ENDPOINT` (no matching field) and `AZURE_CLIENT_ID` (consumed by the Azure SDK credential, intended).

---

## (Y) What infra SETS on the backend Container App

`v2/infra/main.bicep`, `backendContainerApp` module, `env: union([...static...], enableMonitoring ? [...] : [])`.

| # | env var | bicep line | value source |
|---|---------|-----------|--------------|
| 1 | `AZURE_CLIENT_ID` | L1810 | `userAssignedIdentity.outputs.clientId` |
| 2 | `AZURE_UAMI_CLIENT_ID` | L1811 | `userAssignedIdentity.outputs.clientId` |
| 3 | `AZURE_TENANT_ID` | L1812 | `subscription().tenantId` |
| 4 | `AZURE_ENVIRONMENT` | L1821 | `'production'` (static) |
| 5 | `AZURE_AI_PROJECT_ENDPOINT` | L1823 | `aiProject.outputs.projectEndpoint` |
| 6 | `AZURE_OPENAI_ENDPOINT` | L1824 | `effectiveOpenAiEndpoint` |
| 7 | `AZURE_AI_SERVICES_ENDPOINT` | L1827 | `aiServices.outputs.endpoint` |
| 8 | `AZURE_OPENAI_API_VERSION` | L1828 | `azureOpenAiApiVersion` |
| 9 | `AZURE_AI_AGENT_API_VERSION` | L1829 | `azureAiAgentApiVersion` |
| 10 | `AZURE_OPENAI_GPT_DEPLOYMENT` | L1836 | `gptModelName` |
| 11 | `AZURE_OPENAI_REASONING_DEPLOYMENT` | L1837 | `reasoningModelName` |
| 12 | `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` | L1838 | `embeddingModelName` |
| 13 | `AZURE_DB_TYPE` | L1846 | `databaseType` |
| 14 | `AZURE_INDEX_STORE` | L1847 | `indexStoreValue` |
| 15 | `AZURE_COSMOS_ENDPOINT` | L1848 | `effectiveCosmosEndpoint` |
| 16 | `AZURE_AI_SEARCH_ENDPOINT` | L1849 | `effectiveSearchEndpoint` |
| 17 | `AZURE_AI_SEARCH_KNOWLEDGE_BASE_NAME` | L1856 | `searchKnowledgeBaseName` |
| 18 | `AZURE_AI_SEARCH_KNOWLEDGE_SOURCE_NAME` | L1857 | `searchKnowledgeSourceName` |
| 19 | `AZURE_AI_SEARCH_KNOWLEDGE_BASE_API_VERSION` | L1858 | `searchKnowledgeBaseApiVersion` |
| 20 | `AZURE_AI_SEARCH_CONNECTION_NAME` | L1863 | `databaseType=='cosmosdb' ? '${kb}-mcp' : ''` |
| 21 | `AZURE_POSTGRES_ENDPOINT` | L1864 | `postgresLibpqUri` |
| 22 | `AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME` | L1865 | `databaseType=='postgresql' ? 'id-<suffix>' : ''` |
| 23 | `AZURE_SPEECH_SERVICE_NAME` | L1870 | `speechService.outputs.name` |
| 24 | `AZURE_SPEECH_SERVICE_REGION` | L1871 | `azureAiServiceLocation` |
| 25 | `AZURE_SPEECH_ACCOUNT_RESOURCE_ID` | L1872 | `speechService.outputs.resourceId` |
| 26 | `AZURE_CONTENT_SAFETY_ENABLED` | L1878 | `'true'` (static) |
| 27 | `AZURE_CONTENT_SAFETY_ENDPOINT` | L1879 | `cogContentSafety.outputs.endpoint` |
| 28 | `CWYD_ORCHESTRATOR_NAME` | L1884 | `databaseType=='postgresql' ? 'langgraph' : 'agent_framework'` |
| 29 | `AZURE_STORAGE_ACCOUNT_NAME` | L1893 | `effectiveStorageName` |
| 30 | `AZURE_DOCUMENTS_CONTAINER` | L1894 | `documentsContainerName` |
| 31 | `AZURE_DOC_PROCESSING_QUEUE` | L1895 | `docProcessingQueueName` |
| 32 | `AZURE_INGESTION_TRIGGER` | L1900 | `ingestionTrigger` |
| 33 | `AZURE_APP_INSIGHTS_CONNECTION_STRING` | L1912 | `applicationInsights!.outputs.connectionString` **(only when `enableMonitoring`)** |

Direct `os.environ`/`os.getenv` outside settings.py: **none** (grep found only two doc-comment mentions in `app.py` L244 and `settings.py` L532). All config flows through typed `BaseSettings`.

---

## (X) What the backend READS — every settings field

`env_prefix` + field name → env var. "In Y?" = set in the table above.

### `AppSettings` (root, `env_prefix="AZURE_"`)
| field | env var | line | required? | default | in Y? |
|-------|---------|------|-----------|---------|-------|
| `solution_suffix` | `AZURE_SOLUTION_SUFFIX` | L517 | optional | `""` | ❌ |
| `resource_group` | `AZURE_RESOURCE_GROUP` | L518 | optional | `""` | ❌ |
| `location` | `AZURE_LOCATION` | L519 | optional | `""` | ❌ |
| `ai_service_location` | `AZURE_AI_SERVICE_LOCATION` | L520 | optional | `""` | ❌ |
| `environment` | `AZURE_ENVIRONMENT` | L534 | optional | `LOCAL` | ✅ |

### `IdentitySettings` (`env_prefix="AZURE_"`)
| field | env var | line | required? | default | in Y? |
|-------|---------|------|-----------|---------|-------|
| `tenant_id` | `AZURE_TENANT_ID` | L146 | optional | `""` | ✅ |
| `uami_client_id` | `AZURE_UAMI_CLIENT_ID` | L147 | optional | `""` | ✅ |
| `uami_principal_id` | `AZURE_UAMI_PRINCIPAL_ID` | L148 | optional | `""` | ❌ |
| `uami_resource_id` | `AZURE_UAMI_RESOURCE_ID` | L149 | optional | `""` | ❌ |

### `FoundrySettings` (`env_prefix="AZURE_AI_"`)
| field | env var | line | required? | default | in Y? |
|-------|---------|------|-----------|---------|-------|
| `services_endpoint` | `AZURE_AI_SERVICES_ENDPOINT` | L161 | optional | `""` | ✅ |
| `project_endpoint` | `AZURE_AI_PROJECT_ENDPOINT` | L162 | optional | `""` | ✅ |
| `service_location` | `AZURE_AI_SERVICE_LOCATION` | L163 | optional | `""` | ❌ |
| `agent_api_version` | `AZURE_AI_AGENT_API_VERSION` | L164 | optional | `""` | ✅ |

> Note: `AZURE_AI_SERVICE_LOCATION` is read by **two** fields (root `ai_service_location` + `FoundrySettings.service_location`). Neither is set on the container.

### `OpenAISettings` (`env_prefix="AZURE_OPENAI_"`)
| field | env var | line | required? | default | in Y? |
|-------|---------|------|-----------|---------|-------|
| `api_version` | `AZURE_OPENAI_API_VERSION` | L172 | optional | `""` | ✅ |
| `gpt_deployment` | `AZURE_OPENAI_GPT_DEPLOYMENT` | L173 | optional | `""` | ✅ |
| `reasoning_deployment` | `AZURE_OPENAI_REASONING_DEPLOYMENT` | L174 | optional | `""` | ✅ |
| `embedding_deployment` | `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` | L175 | optional | `""` | ✅ |
| `embedding_dimensions` | `AZURE_OPENAI_EMBEDDING_DIMENSIONS` | L176 | optional | `1536` | ❌ |
| `temperature` | `AZURE_OPENAI_TEMPERATURE` | L177 | optional | `0.0` | ❌ |
| `max_tokens` | `AZURE_OPENAI_MAX_TOKENS` | L178 | optional | `1000` | ❌ |

> **No `endpoint` field exists.** `AZURE_OPENAI_ENDPOINT` (set at Y#6) is therefore **unread**. The FoundryIQ LLM provider builds the OpenAI base URL from `foundry.services_endpoint + "/openai/v1"` (`v2/src/backend/core/providers/llm/foundry_iq.py` L281–289), not from `AZURE_OPENAI_ENDPOINT`.

### `DatabaseSettings` (`env_prefix="AZURE_"`)
| field | env var | line | required? | default | in Y? |
|-------|---------|------|-----------|---------|-------|
| `db_type` | `AZURE_DB_TYPE` | L197 | optional | `cosmosdb` | ✅ |
| `index_store` | `AZURE_INDEX_STORE` | L198 | optional | `AzureSearch` | ✅ |
| `cosmos_endpoint` | `AZURE_COSMOS_ENDPOINT` | L201 | **required in cosmosdb mode** (validator) | `""` | ✅ |
| `cosmos_account_name` | `AZURE_COSMOS_ACCOUNT_NAME` | L202 | optional | `""` | ❌ |
| `cosmos_database_name` | `AZURE_COSMOS_DATABASE_NAME` | L203 | optional | `"cwyd"` | ❌ |
| `cosmos_container_name` | `AZURE_COSMOS_CONTAINER_NAME` | L204 | optional | `"conversations"` | ❌ |
| `postgres_endpoint` | `AZURE_POSTGRES_ENDPOINT` | L207 | **required in postgresql mode** (validator) | `""` | ✅ |
| `postgres_host` | `AZURE_POSTGRES_HOST` | L208 | optional | `""` | ❌ |
| `postgres_name` | `AZURE_POSTGRES_NAME` | L209 | optional | `""` | ❌ |
| `postgres_admin_principal_name` | `AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME` | L210 | optional | `""` | ✅ |

### `SearchSettings` (`env_prefix="AZURE_AI_SEARCH_"`)
| field | env var | line | required? | default | in Y? |
|-------|---------|------|-----------|---------|-------|
| `endpoint` | `AZURE_AI_SEARCH_ENDPOINT` | L250 | optional | `""` | ✅ |
| `name` | `AZURE_AI_SEARCH_NAME` | L251 | optional | `""` | ❌ |
| `index` | `AZURE_AI_SEARCH_INDEX` | L252 | optional | `"cwyd-index"` | ❌ (default matches provisioned) |
| `use_semantic_search` | `AZURE_AI_SEARCH_USE_SEMANTIC_SEARCH` | L253 | optional | `True` | ❌ |
| `top_k` | `AZURE_AI_SEARCH_TOP_K` | L254 | optional | `5` | ❌ |
| `knowledge_base_name` | `AZURE_AI_SEARCH_KNOWLEDGE_BASE_NAME` | L260 | optional | `"cwyd-kb"` | ✅ |
| `knowledge_source_name` | `AZURE_AI_SEARCH_KNOWLEDGE_SOURCE_NAME` | L261 | optional | `"cwyd-index-ks"` | ✅ |
| `knowledge_base_api_version` | `AZURE_AI_SEARCH_KNOWLEDGE_BASE_API_VERSION` | L262 | optional | `"2025-11-01-preview"` | ✅ |
| `connection_name` | `AZURE_AI_SEARCH_CONNECTION_NAME` | L267 | optional | `""` | ✅ |

### `StorageSettings` (`env_prefix="AZURE_"`)
| field | env var | line | required? | default | in Y? |
|-------|---------|------|-----------|---------|-------|
| `storage_account_name` | `AZURE_STORAGE_ACCOUNT_NAME` | L275 | optional | `""` | ✅ |
| `storage_blob_endpoint` | `AZURE_STORAGE_BLOB_ENDPOINT` | L276 | optional | `""` | ❌ (derived from account name) |
| `documents_container` | `AZURE_DOCUMENTS_CONTAINER` | L277 | optional | `""` | ✅ |
| `doc_processing_queue` | `AZURE_DOC_PROCESSING_QUEUE` | L278 | optional | `""` | ✅ |
| `ingestion_trigger` | `AZURE_INGESTION_TRIGGER` | L279 | optional | `DIRECT_ENQUEUE` | ✅ |

### `ObservabilitySettings` (`env_prefix="AZURE_"`)
| field | env var | line | required? | default | in Y? |
|-------|---------|------|-----------|---------|-------|
| `app_insights_connection_string` | `AZURE_APP_INSIGHTS_CONNECTION_STRING` | L287 | optional | `""` | ✅ (only when `enableMonitoring`) |
| `log_level` | `AZURE_LOG_LEVEL` | L288 | optional | `"INFO"` | ❌ |

### `NetworkSettings` (`env_prefix="AZURE_"`)
| field | env var | line | required? | default | in Y? |
|-------|---------|------|-----------|---------|-------|
| `backend_url` | `AZURE_BACKEND_URL` | L296 | optional | `""` | ❌ |
| `frontend_url` | `AZURE_FRONTEND_URL` | L297 | optional | `""` | ❌ |
| `function_app_url` | `AZURE_FUNCTION_APP_URL` | L298 | optional | `""` | ❌ |
| `function_app_name` | `AZURE_FUNCTION_APP_NAME` | L299 | optional | `""` | ❌ |
| `vnet_name` | `AZURE_VNET_NAME` | L300 | optional | `""` | ❌ |
| `vnet_resource_id` | `AZURE_VNET_RESOURCE_ID` | L301 | optional | `""` | ❌ |
| `bastion_name` | `AZURE_BASTION_NAME` | L302 | optional | `""` | ❌ |
| `cors_origins` | **`BACKEND_CORS_ORIGINS`** (bare; `AliasChoices`, no `AZURE_` prefix) | L317–319 | optional | `[]` | ❌ |

### `OrchestratorSettings` (`env_prefix="CWYD_ORCHESTRATOR_"`)
| field | env var | line | required? | default | in Y? |
|-------|---------|------|-----------|---------|-------|
| `name` | `CWYD_ORCHESTRATOR_NAME` | L389 | optional | `AGENT_FRAMEWORK` | ✅ |

### `ContentSafetySettings` (`env_prefix="AZURE_CONTENT_SAFETY_"`)
| field | env var | line | required? | default | in Y? |
|-------|---------|------|-----------|---------|-------|
| `endpoint` | `AZURE_CONTENT_SAFETY_ENDPOINT` | L430 | optional | `""` | ✅ |
| `enabled` | `AZURE_CONTENT_SAFETY_ENABLED` | L431 | optional | `True` | ✅ |
| `severity_threshold` | `AZURE_CONTENT_SAFETY_SEVERITY_THRESHOLD` | L432 | optional | `4` | ❌ |

### `SpeechSettings` (`env_prefix="AZURE_SPEECH_"`)
| field | env var | line | required? | default | in Y? |
|-------|---------|------|-----------|---------|-------|
| `service_name` | `AZURE_SPEECH_SERVICE_NAME` | L461 | optional | `""` | ✅ |
| `service_region` | `AZURE_SPEECH_SERVICE_REGION` | L462 | optional | `""` | ✅ |
| `account_resource_id` | `AZURE_SPEECH_ACCOUNT_RESOURCE_ID` | L463 | optional | `""` | ✅ |
| `recognizer_languages` | `AZURE_SPEECH_RECOGNIZER_LANGUAGES` | L464 | optional | `"en-US,fr-FR,de-DE,it-IT"` | ❌ |

### `DocumentIntelligenceSettings` (`env_prefix="AZURE_DOCUMENT_INTELLIGENCE_"`)
| field | env var | line | required? | default | in Y? |
|-------|---------|------|-----------|---------|-------|
| `api_version` | `AZURE_DOCUMENT_INTELLIGENCE_API_VERSION` | L498 | optional | `"2024-11-30"` | ❌ |
| `model_id` | `AZURE_DOCUMENT_INTELLIGENCE_MODEL_ID` | L499 | optional | `"prebuilt-layout"` | ❌ |

---

## DIFF — Table 1: MISSING & REQUIRED (crash / hard-degrade at boot)

**EMPTY.** No required var is missing.

Rationale: every field carries a safe default (`""` / typed). The only boot-time enforcement is `DatabaseSettings._enforce_mode_consistency` (settings.py L212–243), which in the default `cosmosdb` mode requires `AZURE_COSMOS_ENDPOINT` (set, Y#15) and `AZURE_INDEX_STORE == AzureSearch` (set, Y#14). In `postgresql` mode it requires `AZURE_POSTGRES_ENDPOINT` (set, Y#21). Both branches are satisfied, so `AppSettings()` never raises and the backend starts. **The backend is not failing to boot.**

---

## DIFF — Table 2: MISSING & OPTIONAL (silent dev/local fallback in cloud)

Sorted by runtime impact.

| env var | settings line | reads default | actually consumed? | wrong-for-cloud? | impact |
|---------|---------------|---------------|--------------------|------------------|--------|
| **`BACKEND_CORS_ORIGINS`** | L317 | `[]` | **yes** — `app.py` L251 | **YES** | `cors_origins` empty → `create_app()` falls back to `allow_origins=["*"]` with `allow_credentials=False`. Cross-origin credentialed calls from the App Service frontend to the ACA backend are not honored; `GET /api/admin/status` reports `cors_origins: []`. **#1 "missing variable" symptom.** |
| `AZURE_AI_SEARCH_INDEX` | L252 | `"cwyd-index"` | **yes** — `azure_search.py` L97/203/250/… | no (default == provisioned name) | Works **only by coincidence** — the default equals the provisioned index `cwyd-index` (confirmed in `.azure/.../.env` + provision log). Fragile: if infra ever renames the index, the backend silently queries the wrong/empty index → "no results / empty answers". |
| `AZURE_AI_SERVICE_LOCATION` | L520 + L163 | `""` | **no** (no consumer found) | n/a | Informational only. Surfaces as blank in admin/diagnostics. No functional impact. |
| `AZURE_SOLUTION_SUFFIX` | L517 | `""` | no | n/a | Admin/display only. Blank in cloud. |
| `AZURE_RESOURCE_GROUP` | L518 | `""` | no | n/a | Admin/display only. |
| `AZURE_LOCATION` | L519 | `""` | no | n/a | Admin/display only. |
| `AZURE_UAMI_PRINCIPAL_ID` | L148 | `""` | no (credentials use `uami_client_id`) | n/a | Informational. |
| `AZURE_UAMI_RESOURCE_ID` | L149 | `""` | no | n/a | Informational. |
| `AZURE_COSMOS_ACCOUNT_NAME` | L202 | `""` | no (cosmos client uses `cosmos_endpoint`) | n/a | Informational. |
| `AZURE_COSMOS_DATABASE_NAME` | L203 | `"cwyd"` | yes | no (default OK) | Default matches provisioned DB. |
| `AZURE_COSMOS_CONTAINER_NAME` | L204 | `"conversations"` | yes | no (default OK) | Default matches provisioned container. |
| `AZURE_POSTGRES_HOST` | L208 | `""` | no (postgres uses `postgres_endpoint` libpq URI) | n/a | Informational (postgresql mode). |
| `AZURE_POSTGRES_NAME` | L209 | `""` | no | n/a | Informational (postgresql mode). |
| `AZURE_AI_SEARCH_NAME` | L251 | `""` | no (search uses `endpoint`+`index`) | n/a | Informational. |
| `AZURE_STORAGE_BLOB_ENDPOINT` | L276 | `""` | yes — `resolve_storage_endpoints` | no in public cloud | Falls back to `https://{account}.blob.core.windows.net` derived from `AZURE_STORAGE_ACCOUNT_NAME` (set). Only matters in sovereign clouds. |
| `AZURE_BACKEND_URL` | L296 | `""` | no | n/a | Self-URL; no consumer. Bicep emits it as an **output** (L2581) → azd `.env` only, not the container. |
| `AZURE_FRONTEND_URL` | L297 | `""` | no | n/a | No consumer (CORS uses the separate bare alias). Bicep **output** L2584 → azd `.env` only. |
| `AZURE_FUNCTION_APP_URL` | L298 | `""` | no | n/a | Informational. |
| `AZURE_FUNCTION_APP_NAME` | L299 | `""` | no | n/a | Informational. |
| `AZURE_VNET_NAME` / `AZURE_VNET_RESOURCE_ID` / `AZURE_BASTION_NAME` | L300–302 | `""` | no | n/a | Informational. |
| `AZURE_LOG_LEVEL` | L288 | `"INFO"` | yes | no (default OK) | INFO is the intended cloud level. |
| `AZURE_OPENAI_EMBEDDING_DIMENSIONS` | L176 | `1536` | yes | no (matches model) | Default matches `text-embedding` 1536. |
| `AZURE_OPENAI_TEMPERATURE` | L177 | `0.0` | yes | no | Intended default. |
| `AZURE_OPENAI_MAX_TOKENS` | L178 | `1000` | yes | no | Intended default. |
| `AZURE_AI_SEARCH_USE_SEMANTIC_SEARCH` | L253 | `True` | yes | no | Intended default. |
| `AZURE_AI_SEARCH_TOP_K` | L254 | `5` | yes | no | Intended default. |
| `AZURE_CONTENT_SAFETY_SEVERITY_THRESHOLD` | L432 | `4` | yes | no | Intended default. |
| `AZURE_SPEECH_RECOGNIZER_LANGUAGES` | L464 | `"en-US,fr-FR,de-DE,it-IT"` | yes — `speech.py` L75 | no | Intended default. |
| `AZURE_DOCUMENT_INTELLIGENCE_API_VERSION` | L498 | `"2024-11-30"` | yes | no | Intended default. |
| `AZURE_DOCUMENT_INTELLIGENCE_MODEL_ID` | L499 | `"prebuilt-layout"` | yes | no | Intended default. |

---

## DIFF — Table 3: NAME MISMATCH (set under one name, read under another)

| infra sets | bicep line | backend reads | settings line | verdict |
|------------|-----------|---------------|---------------|---------|
| `AZURE_OPENAI_ENDPOINT` | L1824 | *(no field)* — `OpenAISettings` has no `endpoint`; backend uses `foundry.services_endpoint` (`AZURE_AI_SERVICES_ENDPOINT`) | — | **Set but unread.** Harmless: the OpenAI base URL is derived from `services_endpoint + /openai/v1`. The value is silently ignored, but the feature is served by another (correctly wired) var. |
| `AZURE_CLIENT_ID` | L1810 | *(no field)* — consumed by Azure SDK `ManagedIdentityCredential`/`DefaultAzureCredential` auto-resolution | — | **Intended.** Not a settings field; the SDK reads `AZURE_CLIENT_ID` directly to pin the UAMI. `uami_client_id` (the settings twin) is also set (Y#2). No mismatch in effect. |
| *(nothing)* | — | `BACKEND_CORS_ORIGINS` (bare alias; `cors_origins` deliberately drops the `AZURE_` prefix) | L317 | **Prefix subtlety, not a rename.** Bicep sets no variant at all → see Table 2 row 1. Because the field uses `validation_alias=AliasChoices("BACKEND_CORS_ORIGINS", "cors_origins")`, an `AZURE_CORS_ORIGINS` would NOT be picked up either — the value MUST be set under the bare name. |

No true "set under wrong name, value lost into a feature" mismatch exists beyond the CORS prefix subtlety.

---

## Step 5 — load-bearing values cross-check (all green)

| concern | bicep var | bicep line | container env | settings field reading it | matched? |
|---------|-----------|-----------|---------------|----------------------------|----------|
| Foundry project endpoint | `aiProject.outputs.projectEndpoint` | L1823 | `AZURE_AI_PROJECT_ENDPOINT` | `foundry.project_endpoint` | ✅ |
| Foundry/AI Services endpoint | `aiServices.outputs.endpoint` | L1827 | `AZURE_AI_SERVICES_ENDPOINT` | `foundry.services_endpoint` (+ OpenAI base URL) | ✅ |
| GPT deployment | `gptModelName='gpt-5.1'` | L1836 / param L134 | `AZURE_OPENAI_GPT_DEPLOYMENT` | `openai.gpt_deployment` | ✅ |
| Reasoning deployment | `reasoningModelName` | L1837 | `AZURE_OPENAI_REASONING_DEPLOYMENT` | `openai.reasoning_deployment` | ✅ |
| Embedding deployment | `embeddingModelName` | L1838 | `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` | `openai.embedding_deployment` | ✅ |
| Search endpoint | `effectiveSearchEndpoint` | L1849 / def L1045 | `AZURE_AI_SEARCH_ENDPOINT` | `search.endpoint` | ✅ |
| Index store selection | `indexStoreValue` (`cosmosdb→AzureSearch`) | L1847 / def L1617 | `AZURE_INDEX_STORE` | `database.index_store` | ✅ |
| DB type | `databaseType='cosmosdb'` | L1846 / param L86 | `AZURE_DB_TYPE` | `database.db_type` | ✅ |
| Cosmos endpoint | `effectiveCosmosEndpoint` | L1848 / def L1445 | `AZURE_COSMOS_ENDPOINT` | `database.cosmos_endpoint` | ✅ |
| Postgres endpoint | `postgresLibpqUri` | L1864 / def L1614 | `AZURE_POSTGRES_ENDPOINT` | `database.postgres_endpoint` | ✅ |
| Storage account | `effectiveStorageName` | L1893 / def L1316 | `AZURE_STORAGE_ACCOUNT_NAME` | `storage.storage_account_name` (blob/queue endpoints derived) | ✅ |
| Documents container | `documentsContainerName` | L1894 | `AZURE_DOCUMENTS_CONTAINER` | `storage.documents_container` | ✅ |
| Processing queue | `docProcessingQueueName` | L1895 | `AZURE_DOC_PROCESSING_QUEUE` | `storage.doc_processing_queue` | ✅ |
| Orchestrator | `cosmosdb→agent_framework` | L1884 | `CWYD_ORCHESTRATOR_NAME` | `orchestrator.name` | ✅ |
| Identity (settings) | `userAssignedIdentity.outputs.clientId` | L1811 | `AZURE_UAMI_CLIENT_ID` | `identity.uami_client_id` (used in `app.py` L78, `managed_identity.py` L23) | ✅ |
| Identity (SDK) | `userAssignedIdentity.outputs.clientId` | L1810 | `AZURE_CLIENT_ID` | SDK credential auto-resolution | ✅ |
| Tenant | `subscription().tenantId` | L1812 | `AZURE_TENANT_ID` | `identity.tenant_id` | ✅ |

Every data-store / model / identity / orchestrator value is set in bicep AND read under the same name. **The backend can reach OpenAI/Foundry, Search, Cosmos/Postgres, and Storage.**

---

## (b) Ranked list — most likely behind "backend seems missing variables"

1. **`BACKEND_CORS_ORIGINS` (missing).** The only functionally-impactful missing var. Empty → wildcard CORS with credentials disabled; visible as `cors_origins: []` in `GET /api/admin/status`. This is the known CORS issue and the strongest match for the symptom.
2. **`AZURE_AI_SEARCH_INDEX` (missing, default-coincidence).** Not currently broken (default `cwyd-index` == provisioned index), but it reads "missing" in any env dump and is one infra rename away from silently breaking retrieval. Worth pinning explicitly.
3. **Admin-display cluster (missing, no runtime impact):** `AZURE_SOLUTION_SUFFIX`, `AZURE_RESOURCE_GROUP`, `AZURE_LOCATION`, `AZURE_AI_SERVICE_LOCATION`, `AZURE_UAMI_PRINCIPAL_ID`, `AZURE_UAMI_RESOURCE_ID`, `AZURE_COSMOS_ACCOUNT_NAME`, `AZURE_FUNCTION_APP_NAME`, `AZURE_BACKEND_URL`, `AZURE_FRONTEND_URL`. These read empty in the cloud and make the running config *look* half-populated (the likely source of the "seems missing" impression) even though nothing functional depends on them.
4. **Set-but-unread (not missing, but confusing in a dump):** `AZURE_OPENAI_ENDPOINT` (no matching field). If the user diffed bicep-vs-code by name they'd see this as "extra," not "missing."

> Everything else in Table 2 is an intended default that is correct for the cloud (model params, top-k, semantic search, content-safety threshold, speech languages, doc-intelligence pins, log level, cosmos db/container names, derived storage blob endpoint).

## (c) One-line fixes (deterministic values, by bicep line)

Insert into the **static** portion of the backend `env` array (after the `AZURE_INGESTION_TRIGGER` entry at L1900, before the array close at ~L1901):

1. **CORS (highest priority).** Use a cycle-free literal hostname (do NOT reference `frontendWebApp.outputs.*` from the backend container — the frontend module is declared later and the frontend already needs the backend URL, which would risk a module-output cycle). The frontend App Service name is `frontendAppName = 'app-frontend-${solutionSuffix}'` (L1948), whose default hostname is `<name>.azurewebsites.net`:
   ```bicep
   { name: 'BACKEND_CORS_ORIGINS', value: 'https://app-frontend-${solutionSuffix}.azurewebsites.net' }
   ```
   (If a custom domain is in play, set the full origin list comma-separated; the field validator already splits on commas.)

2. **Pin the search index name (defensive).** Hoist a `var searchIndexName = 'cwyd-index'` near the other search vars and add:
   ```bicep
   { name: 'AZURE_AI_SEARCH_INDEX', value: searchIndexName }
   ```
   (Currently relies on the settings default `cwyd-index` matching the provisioned index — make it explicit so an index rename can't silently break retrieval.)

3. **Optional — admin/diagnostic completeness** (no functional change, removes the "looks half-configured" impression). Add as static entries:
   ```bicep
   { name: 'AZURE_SOLUTION_SUFFIX', value: solutionSuffix }
   { name: 'AZURE_RESOURCE_GROUP', value: resourceGroup().name }
   { name: 'AZURE_LOCATION', value: location }
   { name: 'AZURE_AI_SERVICE_LOCATION', value: azureAiServiceLocation }
   ```

No change is needed for any data-store, model, identity, or orchestrator var — they are already correctly wired (Step 5).

---

## Sources

- `v2/src/backend/core/settings.py` (full read; line numbers cited).
- `v2/src/backend/app.py` L233–260 (`create_app` CORS wiring from `NetworkSettings.cors_origins`).
- `v2/src/backend/models/admin.py` L99–121 (`AdminStatus` surfaces `cors_origins`, `db_type`, `index_store`, `environment`, deployments).
- `v2/src/backend/core/providers/llm/foundry_iq.py` L227–289 (OpenAI base URL from `services_endpoint`, not `AZURE_OPENAI_ENDPOINT`).
- `v2/src/backend/core/providers/credentials/{managed_identity.py L23, registry.py L15, __init__.py L13}` + `app.py` L78 (`uami_client_id` consumer).
- `v2/src/backend/core/providers/databases/{cosmosdb.py L165, postgres.py L308}` (only `*_endpoint` consumed).
- `v2/src/backend/core/providers/search/azure_search.py` L96–97 (`endpoint` + `index` consumed).
- `v2/src/functions/core/storage_endpoints.py` L24–54 (`resolve_storage_endpoints`: prefers `storage_blob_endpoint`, derives from `storage_account_name`).
- `v2/infra/main.bicep`: backend env array L1808–1912; var defs `effectiveOpenAiEndpoint` L703, `effectiveSearchEndpoint`/`effectiveSearchName` L1044–1045, `effectiveStorageName` L1316, `effectiveStorageBlobEndpoint` L1318, `effectiveCosmosEndpoint` L1445, `postgresLibpqUri` L1614, `indexStoreValue` L1617; params `databaseType` L86, `ingestionTrigger` L97, `gptModelName` L134, `azureOpenAiApiVersion` L187, `azureAiAgentApiVersion` L190; outputs `AZURE_AI_SERVICE_LOCATION` L2452, `AZURE_OPENAI_ENDPOINT` L2480, `AZURE_STORAGE_BLOB_ENDPOINT` L2567, `AZURE_BACKEND_URL` L2581, `AZURE_FRONTEND_URL` L2584.
- `v2/.azure/cwyd-cdb-v2/.env` + `v2/.scratch/azd-provision.log` ("search index 'cwyd-index' already exists") — confirms provisioned index name == settings default.
