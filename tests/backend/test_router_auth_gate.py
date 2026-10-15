"""Router-level authentication-gate coverage.

Every protected API router mounts
:func:`backend.dependencies.require_authenticated_user` as a router-level
dependency so an unauthenticated caller is rejected with 401 before any
handler runs (the gate's behavior itself is exercised in
``test_admin_auth.py``). ``/api/health`` is deliberately excluded so it
stays a public liveness probe.
"""

from fastapi import APIRouter

from backend.dependencies import require_authenticated_user
from backend.routers import admin, conversation, files, health, history, speech


def _has_auth_gate(router: APIRouter) -> bool:
    """Whether the router mounts the auth gate as a router dependency."""
    return any(
        getattr(dependant, "dependency", None) is require_authenticated_user
        for dependant in router.dependencies
    )


def test_protected_routers_mount_the_auth_gate() -> None:
    for module in (admin, conversation, files, history, speech):
        assert _has_auth_gate(
            module.router
        ), f"{module.__name__} must mount require_authenticated_user"


def test_health_router_is_public() -> None:
    assert not _has_auth_gate(health.router)
