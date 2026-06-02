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
