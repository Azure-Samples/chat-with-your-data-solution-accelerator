/**
 * Wire shapes for the v2 admin REST surface. Mirrors
 * `src/backend/models/admin.py`. Sanitized snapshot fields only --
 * no secrets cross the type boundary.
 */

/**
 * First-party orchestrator registry keys. Mirrors the backend
 * `OrchestratorName` StrEnum in `backend/core/settings.py`. The wire
 * field `orchestrator_name` stays a plain `string` because the backend
 * type is widened to `OrchestratorName | str` for third-party registry
 * keys; this closed set is the list of built-in choices the admin
 * Orchestrator dropdown offers.
 */
export const OrchestratorName = {
  LangGraph: "langgraph",
  AgentFramework: "agent_framework",
} as const;
export type OrchestratorName =
  (typeof OrchestratorName)[keyof typeof OrchestratorName];

/**
 * Standard Python logging levels offered by the admin Log level
 * dropdown. The wire field `log_level` stays a plain `string` because
 * the backend stores it as a free-form logging level name; this closed
 * set is the list of built-in levels the dropdown presents.
 */
export const LogLevel = {
  Debug: "DEBUG",
  Info: "INFO",
  Warning: "WARNING",
  Error: "ERROR",
} as const;
export type LogLevel = (typeof LogLevel)[keyof typeof LogLevel];

/**
 * Built-in Assistant Type presets offered by the admin Configuration
 * page. Mirrors the backend `AssistantType` StrEnum in
 * `backend/core/agents/presets.py`. Unlike `orchestrator_name` /
 * `log_level`, the backend keeps `ai_assistant_type` a hard StrEnum
 * (no `str` widening) -- this closed set is the exact wire vocabulary.
 * Selecting one loads its persona body (from `assistant_type_presets`)
 * into the editable Answering-prompt field.
 */
export const AssistantType = {
  Default: "default",
  Contract: "contract assistant",
  Employee: "employee assistant",
} as const;
export type AssistantType =
  (typeof AssistantType)[keyof typeof AssistantType];

/**
 * Read-only `{ assistantType: personaBody }` map the backend ships in
 * the effective-config response so the admin dropdown can repopulate
 * the Answering-prompt textarea on change without a second round-trip.
 * Mirrors `EffectiveAdminConfig.assistant_type_presets` (the keys are
 * `AssistantType` wire strings).
 */
export type AssistantTypePresets = Record<string, string>;

/**
 * Sanitized snapshot of the running backend configuration.
 * Mirrors `backend.models.admin.AdminStatus`; non-secret fields only.
 */
export interface AdminStatus {
  orchestrator_name: string;
  db_type: string;
  index_store: string;
  environment: string;
  foundry_project_endpoint_host: string;
  gpt_deployment: string;
  embedding_deployment: string;
  search_enabled: boolean;
  app_insights_enabled: boolean;
  cors_origins: string[];
  version: string;
}

/**
 * Request body for `POST /api/admin/documents/url`.
 * Mirrors `backend.models.admin.IngestUrlRequest`.
 *
 * `ingestion_job_id` is server-generated when absent (the backend
 * model carries `default_factory=uuid4`), so callers normally send
 * just `{ url }` and let the server stamp the correlation id.
 */
export interface IngestUrlRequest {
  url: string;
  ingestion_job_id?: string;
}

/**
 * Response shape for `POST /api/admin/documents/url`.
 * Mirrors `backend.models.admin.IngestUrlResponse`.
 *
 * The backend downloads the URL, stores it as a blob in the documents
 * container, and lets the same `batch_push` pipeline as file upload
 * index it -- so the receipt mirrors an upload (`filename`, `blob_path`,
 * `queued`) plus the echoed `url`. Indexing is async, so there is no
 * synchronous chunk count.
 */
export interface IngestUrlResponse {
  url: string;
  filename: string;
  blob_path: string;
  ingestion_job_id: string;
  queued: boolean;
}

/**
 * Response shape for `POST /api/admin/documents` (multipart upload).
 * Mirrors `backend.models.admin.UploadResponse`.
 */
export interface UploadResponse {
  filename: string;
  blob_path: string;
  ingestion_job_id: string;
  queued: boolean;
}

/**
 * Response shape for `POST /api/admin/documents/reprocess`.
 * Mirrors `backend.models.admin.ReprocessResponse`. `ingestion_job_id`
 * is `null` when the documents container was empty at fan-out time.
 */
export interface ReprocessResponse {
  ingestion_job_id: string | null;
  enqueued_count: number;
}

/**
 * One distinct ingested source. Mirrors
 * `backend.core.providers.search.base.SourceListing`.
 *
 * `chunk_count` is the number of indexed chunks attached to the
 * source (filename or URL set on the `title` field at ingestion).
 * `last_modified` is the most recent change timestamp when the
 * backend can produce one, `null` otherwise (the pgvector schema
 * has no timestamp column, so that backend always returns `null`).
 */
export interface SourceListing {
  source: string;
  chunk_count: number;
  last_modified: string | null;
}

/**
 * Response shape for `GET /api/admin/documents`. Mirrors
 * `backend.models.admin.ListDocumentsResponse`.
 *
 * `total` always equals `documents.length` for the current
 * single-page response shape -- surfaced as its own field so a
 * future paginated variant can extend without breaking consumers.
 */
export interface ListDocumentsResponse {
  documents: SourceListing[];
  total: number;
}

/**
 * Response shape for `DELETE /api/admin/documents/{source}`. Mirrors
 * `backend.models.admin.DeleteDocumentResponse`.
 *
 * `deleted` is the number of indexed chunks removed; the route
 * returns 404 when no chunks matched, so a 200 response always
 * implies `deleted >= 1`.
 */
export interface DeleteDocumentResponse {
  deleted: number;
}

/**
 * Runtime-toggle subset of `AppSettings` returned by
 * `GET /api/admin/config`. Mirrors `backend.models.admin.AdminConfig`.
 *
 * The selection is the closed set the backend allow-list permits
 * PATCHing -- any new field must be added in lockstep across
 * `AdminConfig`, `RuntimeConfig`, and the `WRITABLE_FIELDS` allow-list
 * (enforced server-side with a 422).
 *
 * `cwyd_agent_instructions` is the system prompt for the primary
 * `CWYD_AGENT`; the GET surfaces the built-in default and the PATCH
 * channel lets an operator persist an override.
 *
 * `ai_assistant_type` is the selected persona preset (`default` /
 * `contract assistant` / `employee assistant`). Selecting one loads
 * its body into `cwyd_agent_instructions` client-side; the field is
 * persisted so the dropdown reflects the last choice on reload.
 *
 * `post_answering_prompt`, `post_answering_enabled`, and
 * `post_answering_filter_message` configure the optional
 * `PostPromptValidator` wired into the chat pipeline. The GET surfaces
 * the env baseline (empty / disabled by default) and the PATCH channel
 * lets an operator turn the validator on, supply a prompt template, and
 * override the rejection message shown to end users.
 */
export interface AdminConfig {
  orchestrator_name: string;
  openai_temperature: number;
  openai_max_tokens: number;
  search_use_semantic_search: boolean;
  search_top_k: number;
  log_level: string;
  content_safety_enabled: boolean;
  cwyd_agent_instructions: string;
  ai_assistant_type: string;
  post_answering_prompt: string;
  post_answering_enabled: boolean;
  post_answering_filter_message: string;
}

/**
 * Provenance of an `EffectiveAdminConfig.sources` entry. Mirrors the
 * backend `ConfigSource` StrEnum in `backend/models/admin.py`.
 *
 * `Env` -- value comes from the env default snapshot.
 * `Override` -- value comes from a persisted `RuntimeConfig` row.
 */
export const ConfigSource = {
  Env: "env",
  Override: "override",
} as const;
export type ConfigSource =
  (typeof ConfigSource)[keyof typeof ConfigSource];

/**
 * Override-resolved config envelope returned by
 * `GET /api/admin/config/effective`. Mirrors the backend
 * `EffectiveAdminConfig` model.
 *
 * `values` is the env default snapshot with any persisted runtime
 * overrides overlaid -- this is what the admin UI loads so a saved
 * override (e.g. the orchestrator choice) is reflected after a reload.
 * `sources` maps each field name to whether the effective value came
 * from the env default or a persisted override. `updated_at` /
 * `updated_by` surface the audit fields of the persisted override, or
 * `null` when no override has been saved.
 *
 * `assistant_type_presets` is the static `{ type: personaBody }` map
 * the dropdown uses to repopulate the Answering-prompt textarea on
 * change; it is read-only and identical across overrides.
 */
export interface EffectiveAdminConfig {
  values: AdminConfig;
  sources: Record<string, ConfigSource>;
  assistant_type_presets: AssistantTypePresets;
  updated_at: string | null;
  updated_by: string | null;
}

/**
 * Persisted runtime overrides returned by `PATCH /api/admin/config`.
 * Mirrors `backend.core.types.RuntimeConfig`.
 *
 * Every toggle field is `T | null` -- `null` means "not overridden,
 * fall through to the env default surfaced by `GET /api/admin/config`".
 * `updated_at` / `updated_by` are server-set audit fields the backend
 * stamps on every successful PATCH.
 */
export interface RuntimeConfig {
  orchestrator_name: string | null;
  openai_temperature: number | null;
  openai_max_tokens: number | null;
  search_use_semantic_search: boolean | null;
  search_top_k: number | null;
  log_level: string | null;
  content_safety_enabled: boolean | null;
  cwyd_agent_instructions: string | null;
  ai_assistant_type: string | null;
  post_answering_prompt: string | null;
  post_answering_enabled: boolean | null;
  post_answering_filter_message: string | null;
  updated_at: string;
  updated_by: string;
}

/**
 * Request body for `PATCH /api/admin/config`. RFC 7396 JSON Merge
 * Patch over the same surface as `AdminConfig`.
 *
 * Semantics enforced by the backend:
 *   * Absent key      -> existing override unchanged.
 *   * Explicit `null` -> override cleared (field reverts to env
 *                       default on next live-reload).
 *   * Explicit value  -> override set or replaced.
 *
 * All fields are optional + nullable so callers can express any
 * subset of the three operations per request.
 */
export interface AdminConfigPatch {
  orchestrator_name?: string | null;
  openai_temperature?: number | null;
  openai_max_tokens?: number | null;
  search_use_semantic_search?: boolean | null;
  search_top_k?: number | null;
  log_level?: string | null;
  content_safety_enabled?: boolean | null;
  cwyd_agent_instructions?: string | null;
  ai_assistant_type?: string | null;
  post_answering_prompt?: string | null;
  post_answering_enabled?: boolean | null;
  post_answering_filter_message?: string | null;
}
