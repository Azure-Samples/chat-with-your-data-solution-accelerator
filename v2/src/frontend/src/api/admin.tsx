/**
 * Pillar: Stable Core
 * Phase: 5 (Admin + Frontend Merge)
 *
 * REST client for the v2 admin surface. Mirrors the hand-rolled
 * `speech.ts` + `streamChat.ts` pattern -- one typed fetch wrapper
 * per endpoint, no OpenAPI generator wired in v2 yet.
 *
 * Backend surface (RBAC-gated on the "admin" role claim via Easy
 * Auth in production; falls back to "local-dev" when env=local).
 */
import type {
  AdminConfig,
  AdminConfigPatch,
  AdminStatus,
  DeleteDocumentResponse,
  IngestUrlRequest,
  IngestUrlResponse,
  ListDocumentsResponse,
  ReprocessResponse,
  RuntimeConfig,
  UploadResponse,
} from "@/models/admin";

const ADMIN_STATUS_URL = "/api/admin/status";
const ADMIN_CONFIG_URL = "/api/admin/config";
const ADMIN_DOCUMENTS_URL = "/api/admin/documents";
const ADMIN_DOCUMENTS_INGEST_URL = "/api/admin/documents/url";
const ADMIN_DOCUMENTS_REPROCESS_URL = "/api/admin/documents/reprocess";

/**
 * Structured object form of FastAPI's `detail` field. The backend
 * 422 RAI gate (`backend.routers.admin.patch_config_endpoint`)
 * stamps `{msg, field, reason}` so callers can render a per-field
 * inline rejection without resorting to regex on the message.
 */
export interface AdminApiErrorDetailObject {
  msg?: string;
  field?: string;
  reason?: string;
}

export type AdminApiErrorDetail = string | AdminApiErrorDetailObject;

export interface AdminApiErrorBody {
  detail?: AdminApiErrorDetail;
}

/**
 * Typed Error thrown by `patchAdminConfig` on a non-2xx response.
 * Exposes the raw HTTP status and the parsed JSON body so callers
 * can branch on 422 RAI rejections vs. 401/403 RBAC vs. 5xx.
 *
 * `body` is `null` when the response body was empty or unparseable.
 */
export class AdminApiError extends Error {
  readonly status: number;
  readonly body: AdminApiErrorBody | null;
  constructor(
    operation: string,
    status: number,
    body: AdminApiErrorBody | null,
  ) {
    super(`${operation}: request failed with status ${status}`);
    this.name = "AdminApiError";
    this.status = status;
    this.body = body;
  }
}

async function parseErrorBody(
  response: Response,
): Promise<AdminApiErrorBody | null> {
  const text = await response.text().catch(() => "");
  if (text === "") {
    return null;
  }
  try {
    return JSON.parse(text) as AdminApiErrorBody;
  } catch {
    return null;
  }
}

/**
 * Fetch the sanitized backend status snapshot.
 *
 * @throws Error when the response status is not 2xx. Callers should
 * distinguish: 401 (missing/malformed Easy Auth in production), 403
 * (authenticated but not in the "admin" role), 5xx (backend down).
 */
export async function getAdminStatus(): Promise<AdminStatus> {
  const response = await fetch(ADMIN_STATUS_URL, {
    method: "GET",
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(
      `getAdminStatus: request failed with status ${response.status}`,
    );
  }
  const body = (await response.json()) as AdminStatus;
  return body;
}

/**
 * Fetch + parse + embed + index a single URL.
 *
 * `ingestion_job_id` is server-generated -- callers pass just the
 * URL and the backend stamps the correlation id surfaced in logs.
 *
 * @throws Error on non-2xx (422 invalid URL shape, 503 storage /
 * search not configured, 401/403 RBAC, 5xx backend down).
 */
export async function addDocumentUrl(url: string): Promise<IngestUrlResponse> {
  const requestBody: IngestUrlRequest = { url };
  const response = await fetch(ADMIN_DOCUMENTS_INGEST_URL, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(requestBody),
  });
  if (!response.ok) {
    throw new Error(
      `addDocumentUrl: request failed with status ${response.status}`,
    );
  }
  const body = (await response.json()) as IngestUrlResponse;
  return body;
}

/**
 * Upload a single document file and enqueue it for indexing.
 *
 * Multipart body with the form key `file` (matches the FastAPI
 * `UploadFile = File(...)` route parameter name).
 *
 * @throws Error on non-2xx (413 oversize, 415 unsupported extension,
 * 422 missing / empty filename, 503 storage not configured,
 * 401/403 RBAC, 5xx backend down).
 */
export async function uploadDocument(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file, file.name);
  const response = await fetch(ADMIN_DOCUMENTS_URL, {
    method: "POST",
    headers: { Accept: "application/json" },
    body: formData,
  });
  if (!response.ok) {
    throw new Error(
      `uploadDocument: request failed with status ${response.status}`,
    );
  }
  const body = (await response.json()) as UploadResponse;
  return body;
}

/**
 * Fan every blob in the documents container onto the push queue so
 * every existing document is re-parsed, re-embedded, and re-pushed
 * through the same pipeline a freshly-uploaded file traverses.
 *
 * @throws Error on non-2xx (503 storage / queue not configured,
 * 401/403 RBAC, 5xx backend down).
 */
export async function reprocessAll(): Promise<ReprocessResponse> {
  const response = await fetch(ADMIN_DOCUMENTS_REPROCESS_URL, {
    method: "POST",
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(
      `reprocessAll: request failed with status ${response.status}`,
    );
  }
  const body = (await response.json()) as ReprocessResponse;
  return body;
}

/**
 * List every distinct source currently indexed. Feeds the admin
 * Delete Data grid with one row per source.
 *
 * The response always carries a `documents` array and a `total`
 * count -- an empty index returns `{ documents: [], total: 0 }`
 * (a valid operating state, not an error).
 *
 * @throws Error on non-2xx (503 search not configured, 401/403 RBAC,
 * 5xx backend / search backend down).
 */
export async function listDocuments(): Promise<ListDocumentsResponse> {
  const response = await fetch(ADMIN_DOCUMENTS_URL, {
    method: "GET",
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(
      `listDocuments: request failed with status ${response.status}`,
    );
  }
  const body = (await response.json()) as ListDocumentsResponse;
  return body;
}

/**
 * Delete every indexed chunk for a single source (filename or URL
 * set on the `title` field at ingestion time).
 *
 * The `source` parameter is URL-encoded before being interpolated
 * into the path. FastAPI's `:path` route converter decodes encoded
 * slashes so nested source paths (`subdir/file.pdf`) work without
 * special handling at the call site.
 *
 * @throws Error on non-2xx (404 source has no indexed chunks,
 * 503 search not configured, 401/403 RBAC, 5xx backend down).
 */
export async function deleteDocument(
  source: string,
): Promise<DeleteDocumentResponse> {
  const url = `${ADMIN_DOCUMENTS_URL}/${encodeURIComponent(source)}`;
  const response = await fetch(url, {
    method: "DELETE",
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(
      `deleteDocument: request failed with status ${response.status}`,
    );
  }
  const body = (await response.json()) as DeleteDocumentResponse;
  return body;
}

/**
 * Fetch the runtime-toggle subset of `AppSettings` (seven canonical
 * fields). The response reflects the live-reloaded effective view
 * -- env defaults overlaid with any persisted runtime overrides.
 *
 * @throws Error on non-2xx (401/403 RBAC, 5xx backend down).
 */
export async function getAdminConfig(): Promise<AdminConfig> {
  const response = await fetch(ADMIN_CONFIG_URL, {
    method: "GET",
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(
      `getAdminConfig: request failed with status ${response.status}`,
    );
  }
  const body = (await response.json()) as AdminConfig;
  return body;
}

/**
 * Apply an RFC 7396 JSON Merge Patch to the persisted
 * `RuntimeConfig` and return the merged shape.
 *
 *   * Absent key      -> existing override unchanged.
 *   * Explicit `null` -> override cleared (field reverts to env
 *                       default on next live-reload).
 *   * Explicit value  -> override set or replaced.
 *
 * The request body is `JSON.stringify`-ed verbatim so explicit
 * `null` values survive the wire (the standard JSON serializer
 * preserves `null`; only `undefined` is dropped). Callers that
 * want to clear an override should set the field to `null`;
 * callers that want to leave it untouched should omit the key.
 *
 * @throws Error on non-2xx (422 unknown field / wrong type,
 * 401/403 RBAC, 5xx backend down).
 */
export async function patchAdminConfig(
  patch: AdminConfigPatch,
): Promise<RuntimeConfig> {
  const response = await fetch(ADMIN_CONFIG_URL, {
    method: "PATCH",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(patch),
  });
  if (!response.ok) {
    const errorBody = await parseErrorBody(response);
    throw new AdminApiError(
      "patchAdminConfig",
      response.status,
      errorBody,
    );
  }
  const body = (await response.json()) as RuntimeConfig;
  return body;
}
