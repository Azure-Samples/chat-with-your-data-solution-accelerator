"""Live health-endpoint checks (integration lane).

Boots the real app against real Azure (see ``conftest.live_app``) and
asserts the diagnostic health contract over a real request. ``/api/health``
is designed to always return 200 so it stays reachable while dependencies
are degraded; ``/api/health/ready`` flips to 503 when a required check fails.
"""

import httpx
import pytest

pytestmark = pytest.mark.integration


async def test_health_endpoint_live_returns_200_with_valid_shape(
    live_client: httpx.AsyncClient,
) -> None:
    """``GET /api/health`` returns 200 with a valid diagnostic snapshot."""
    response = await live_client.get("/api/health")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body.get("status") in {"pass", "degraded", "fail"}, body
    assert body.get("version") == "v2", body
    assert isinstance(body.get("checks"), list), body
    assert body["checks"], "expected at least one dependency check in the snapshot"


async def test_health_ready_live_has_valid_shape(
    live_client: httpx.AsyncClient,
) -> None:
    """``GET /api/health/ready`` answers 200 (ready) or 503 (a required check failed).

    Either way the body must carry the same diagnostic shape. A live,
    correctly configured environment is expected to report 200; 503 is
    accepted so a transiently degraded dependency does not make the lane
    flaky -- the strong always-200 guarantee is asserted on ``/api/health``.
    """
    response = await live_client.get("/api/health/ready")

    assert response.status_code in {200, 503}, response.text
    body = response.json()
    assert body.get("status") in {"pass", "degraded", "fail"}, body
    assert isinstance(body.get("checks"), list), body
