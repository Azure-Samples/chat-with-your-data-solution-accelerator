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

const ADMIN_STATUS_URL = "/api/admin/status";

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
