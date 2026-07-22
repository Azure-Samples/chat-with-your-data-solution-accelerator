"""Health router.

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
(actual round-trip to the SDK) are not performed here.
"""

import logging

from fastapi import APIRouter, Response, status

from backend.dependencies import SettingsDep
from backend.models.health import HealthResponse, OverallStatus
from backend.services.health import run_health_checks

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Diagnostic health snapshot (always 200)",
    description=(
        "Return a full health snapshot of every checked dependency. "
        "Always responds 200 regardless of individual check status, so it "
        "can be scraped for diagnostics without tripping an orchestrator's "
        "restart policy."
    ),
)
async def health(settings: SettingsDep) -> HealthResponse:
    return run_health_checks(settings)


@router.get(
    "/health/ready",
    response_model=HealthResponse,
    summary="Readiness probe (503 on fail)",
    description=(
        "Readiness gate for load balancers and orchestrators. Returns the "
        "same health snapshot, but responds 503 when the overall status is "
        "FAIL so traffic is held back until required dependencies recover."
    ),
    responses={
        503: {
            "model": HealthResponse,
            "description": (
                "Readiness failed; body is the health snapshot with "
                "overall status FAIL."
            ),
        },
    },
)
async def ready(settings: SettingsDep, response: Response) -> HealthResponse:
    result = run_health_checks(settings)
    if result.status is OverallStatus.FAIL:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return result
