"""Live admin-config checks (integration lane).

Pillar: Stable Core
Phase: 6

Drives the admin-gated config endpoints against the real app + real Easy
Auth claims parser (see ``conftest.admin_headers`` / ``non_admin_headers``).
Assertions check the response *shape* and the role gate, never the live
config *values* (Hard Rule #18) -- the deployed orchestrator/model names are
environment-specific and must not be pinned in a tracked test.
"""

import httpx
import pytest

pytestmark = pytest.mark.integration

# The read-only runtime-toggle surface returned by GET /api/admin/config.
_ADMIN_CONFIG_FIELDS = frozenset(
    {
        "orchestrator_name",
        "openai_temperature",
        "openai_max_tokens",
        "search_use_semantic_search",
        "search_top_k",
        "log_level",
        "content_safety_enabled",
        "cwyd_agent_instructions",
        "post_answering_prompt",
        "post_answering_enabled",
        "post_answering_filter_message",
    }
)


async def test_admin_config_live_returns_full_toggle_surface(
    live_client: httpx.AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    """``GET /api/admin/config`` authorizes an admin and returns every toggle."""
    response = await live_client.get("/api/admin/config", headers=admin_headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert _ADMIN_CONFIG_FIELDS <= set(body), _ADMIN_CONFIG_FIELDS - set(body)
    assert isinstance(body["search_top_k"], int), body["search_top_k"]
    assert isinstance(body["content_safety_enabled"], bool), body
    assert body["cwyd_agent_instructions"].strip(), "instructions must be non-empty"


async def test_admin_config_effective_live_returns_values_and_sources(
    live_client: httpx.AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    """``GET /api/admin/config/effective`` returns merged values + provenance."""
    response = await live_client.get(
        "/api/admin/config/effective", headers=admin_headers
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert _ADMIN_CONFIG_FIELDS <= set(body.get("values", {})), body.get("values")
    sources = body.get("sources", {})
    assert _ADMIN_CONFIG_FIELDS <= set(sources), sources
    # Every field's provenance is one of the closed ConfigSource set.
    assert set(sources.values()) <= {"env", "override"}, sources
    # Audit fields are always present (null until a PATCH writes a row).
    assert "updated_at" in body and "updated_by" in body, body


async def test_admin_config_live_forbids_non_admin_role(
    live_client: httpx.AsyncClient,
    non_admin_headers: dict[str, str],
) -> None:
    """A valid but non-admin caller is rejected with 403 in any environment."""
    response = await live_client.get(
        "/api/admin/config", headers=non_admin_headers
    )

    assert response.status_code == 403, response.text
