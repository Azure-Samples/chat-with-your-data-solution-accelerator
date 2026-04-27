"""Health router.

Pillar: Stable Core
Phase: 2

Two endpoints:

- `GET /api/health` -- diagnostic. **Always** returns HTTP 200; the
  body's `status` field carries severity. This keeps the endpoint
  reachable for debugging even when the system is failing.
- `GET /api/health/ready` -- readiness probe for ACA / AKS. Returns
  HTTP 503 when any required check fails so the orchestrator can
  remove the pod from rotation. Optional checks (status `skip`) do
  *not* fail readiness -- pgvector mode legitimately has no separate
  search service.

Each probe is intentionally **shallow**: we verify configuration is
present and the provider can be constructed. Deep liveness probes
(actual round-trip to the SDK) are deferred to Phase 6.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Response, status

from backend.dependencies import SettingsDep
from backend.models.health import DependencyCheck, HealthResponse
from shared.settings import AppSettings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["health"])


def _check_foundry(settings: AppSettings) -> DependencyCheck:
    if not settings.foundry.project_endpoint:
        return DependencyCheck(
            name="foundry_iq",
            status="fail",
            detail="AZURE_AI_PROJECT_ENDPOINT is not set.",
        )
    if not settings.openai.gpt_deployment:
        return DependencyCheck(
            name="foundry_iq",
            status="fail",
            detail="AZURE_OPENAI_GPT_DEPLOYMENT is not set.",
        )
    return DependencyCheck(name="foundry_iq", status="pass")


def _check_database(settings: AppSettings) -> DependencyCheck:
    db = settings.database
    endpoint = (
        db.cosmos_endpoint if db.db_type == "cosmosdb" else db.postgres_endpoint
    )
    if not endpoint:
        return DependencyCheck(
            name="database",
            status="fail",
            detail=f"No endpoint configured for db_type={db.db_type!r}.",
        )
    return DependencyCheck(
        name="database", status="pass", detail=f"db_type={db.db_type}"
    )


def _check_search(settings: AppSettings) -> DependencyCheck:
    if settings.database.index_store == "AzureSearch":
        if not settings.search.endpoint:
            return DependencyCheck(
                name="search",
                status="fail",
                detail="AZURE_AI_SEARCH_ENDPOINT is not set.",
            )
        return DependencyCheck(name="search", status="pass", detail="AzureSearch")
    return DependencyCheck(
        name="search",
        status="skip",
        detail=f"index_store={settings.database.index_store} (no separate search service)",
    )


def _aggregate(checks: list[DependencyCheck]) -> str:
    """Aggregate per-check status into an overall status.

    `skip` is **neutral** -- a check that doesn't apply to this
    deployment mode (e.g. Azure Search in pgvector mode) must not
    drag the overall status down. Reserve `degraded` for future
    optional-check failures.
    """
    if any(c.status == "fail" for c in checks):
        return "fail"
    return "pass"


def _run_checks(settings: AppSettings) -> HealthResponse:
    checks = [
        _check_foundry(settings),
        _check_database(settings),
        _check_search(settings),
    ]
    return HealthResponse(status=_aggregate(checks), checks=checks)


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Diagnostic health snapshot (always 200)",
)
async def health(settings: SettingsDep) -> HealthResponse:
    return _run_checks(settings)


@router.get(
    "/health/ready",
    response_model=HealthResponse,
    summary="Readiness probe (503 on fail)",
)
async def ready(settings: SettingsDep, response: Response) -> HealthResponse:
    result = _run_checks(settings)
    if result.status == "fail":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return result
