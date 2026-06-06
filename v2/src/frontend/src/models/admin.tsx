/**
 * Pillar: Stable Core
 * Phase: 7 (Testing + Documentation)
 *
 * Wire shapes for the v2 admin REST surface. Mirrors
 * `v2/src/backend/models/admin.py`. Sanitized snapshot fields only —
 * no secrets cross the type boundary.
 */

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
  reasoning_deployment: string;
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
 */
export interface IngestUrlResponse {
  ingestion_job_id: string;
  url: string;
  document_count: number;
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
 * Exactly seven v2-canonical fields. The selection is the closed set
 * the backend allow-list permits PATCHing -- any new field must be
 * added in lockstep across `AdminConfig`, `RuntimeConfig`, and the
 * `WRITABLE_FIELDS` allow-list (enforced server-side with a 422).
 */
export interface AdminConfig {
  orchestrator_name: string;
  openai_temperature: number;
  openai_max_tokens: number;
  search_use_semantic_search: boolean;
  search_top_k: number;
  log_level: string;
  content_safety_enabled: boolean;
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
  updated_at: string;
  updated_by: string;
}

/**
 * Request body for `PATCH /api/admin/config`. RFC 7396 JSON Merge
 * Patch over the same seven-field surface as `AdminConfig`.
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
}
