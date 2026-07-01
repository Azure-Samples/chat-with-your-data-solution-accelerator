"""Pillar: Stable Core / Phase: 6 -- tests for v2/src/functions/search_skill/blueprint.py.

Mirrors ``tests/functions/add_url/test_blueprint.py`` for the
HTTP-trigger exception ladder + monkeypatch seam. ``_execute`` is
the seam so tests do not need a real credential or a real Azure
OpenAI embedding deployment.
"""

import json
import logging
from collections.abc import Awaitable, Callable

import azure.functions as func
import pytest
from azure.core.exceptions import AzureError

from backend.core.settings import AppSettings, get_settings
from functions.function_app import app
from functions.search_skill import blueprint as bp_module
from functions.search_skill.blueprint import search_skill
from functions.search_skill.models import (
    SearchSkillOutputData,
    SearchSkillOutputRecord,
    SearchSkillRequest,
    SearchSkillResponse,
)


# Minimal env that satisfies AppSettings + nested cross-field validators.
# Mirrors the fixture in tests/functions/add_url/test_blueprint.py.
_BASE_ENV: dict[str, str] = {
    "AZURE_SOLUTION_SUFFIX": "cwyd001",
    "AZURE_RESOURCE_GROUP": "rg-cwyd-001",
    "AZURE_LOCATION": "eastus2",
    "AZURE_AI_SERVICE_LOCATION": "eastus2",
    "AZURE_TENANT_ID": "00000000-0000-0000-0000-000000000001",
    "AZURE_UAMI_CLIENT_ID": "00000000-0000-0000-0000-000000000002",
    "AZURE_UAMI_PRINCIPAL_ID": "00000000-0000-0000-0000-000000000003",
    "AZURE_UAMI_RESOURCE_ID": "/subscriptions/x/resourceGroups/y/providers/.../id-cwyd001",
    "AZURE_AI_SERVICES_ENDPOINT": "https://ai-cwyd001.services.ai.azure.com/",
    "AZURE_AI_PROJECT_ENDPOINT": "https://ai-cwyd001.services.ai.azure.com/api/projects/proj",
    "AZURE_AI_AGENT_API_VERSION": "2025-05-01",
    "AZURE_OPENAI_API_VERSION": "2024-12-01-preview",
    "AZURE_OPENAI_GPT_DEPLOYMENT": "gpt-5.1",
    "AZURE_OPENAI_EMBEDDING_DEPLOYMENT": "text-embedding-3-small",
    "AZURE_DB_TYPE": "cosmosdb",
    "AZURE_INDEX_STORE": "AzureSearch",
    "AZURE_COSMOS_ENDPOINT": "https://cosmos-cwyd001.documents.azure.com:443/",
    "AZURE_COSMOS_ACCOUNT_NAME": "cosmos-cwyd001",
    "AZURE_AI_SEARCH_ENDPOINT": "https://srch-cwyd001.search.windows.net",
    "AZURE_AI_SEARCH_NAME": "srch-cwyd001",
    "AZURE_STORAGE_ACCOUNT_NAME": "stcwyd001",
    "AZURE_STORAGE_BLOB_ENDPOINT": "",
    "AZURE_DOCUMENTS_CONTAINER": "documents",
    "AZURE_DOC_PROCESSING_QUEUE": "doc-processing",
    "AZURE_BACKEND_URL": "https://ca-back-cwyd001.example.azurecontainerapps.io",
    "AZURE_FRONTEND_URL": "https://app-front-cwyd001.azurewebsites.net",
    "AZURE_FUNCTION_APP_URL": "https://func-cwyd001.azurewebsites.net",
    "AZURE_FUNCTION_APP_NAME": "func-cwyd001",
}


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in _BASE_ENV.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()


def _patch_route_deps(
    monkeypatch: pytest.MonkeyPatch,
    execute: Callable[[SearchSkillRequest, AppSettings], Awaitable[SearchSkillResponse]],
    settings: AppSettings | None = None,
) -> None:
    resolved = settings or AppSettings()
    monkeypatch.setattr(bp_module, "get_settings", lambda: resolved)
    monkeypatch.setattr(bp_module, "_execute", execute)


def _make_req(body: bytes) -> func.HttpRequest:
    return func.HttpRequest(
        method="POST",
        url="/api/search_skill",
        body=body,
        headers={"content-type": "application/json"},
    )


def _wire_request(*records: tuple[str, str]) -> bytes:
    """Build a wire-shape (camelCase ``recordId``) JSON request body."""
    return json.dumps(
        {
            "values": [
                {"recordId": rid, "data": {"text": text}} for rid, text in records
            ]
        }
    ).encode()


@pytest.mark.asyncio
async def test_happy_path_returns_200_with_wire_shape_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected_response = SearchSkillResponse(
        values=[
            SearchSkillOutputRecord(
                recordId="1",
                data=SearchSkillOutputData(embedding=[0.1, 0.2]),
            ),
            SearchSkillOutputRecord(
                recordId="2",
                data=SearchSkillOutputData(embedding=[0.3, 0.4]),
            ),
        ]
    )

    async def fake_execute(
        request: SearchSkillRequest, settings: AppSettings
    ) -> SearchSkillResponse:
        assert [r.record_id for r in request.values] == ["1", "2"]
        assert [r.data.text for r in request.values] == ["hello", "world"]
        return expected_response

    _patch_route_deps(monkeypatch, fake_execute)
    req = _make_req(_wire_request(("1", "hello"), ("2", "world")))

    resp = await search_skill(req)

    assert resp.status_code == 200
    assert resp.mimetype == "application/json"
    payload = json.loads(resp.get_body())
    assert payload == {
        "values": [
            {"recordId": "1", "data": {"embedding": [0.1, 0.2]}},
            {"recordId": "2", "data": {"embedding": [0.3, 0.4]}},
        ]
    }


@pytest.mark.asyncio
async def test_response_excludes_none_errors_and_warnings_on_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default-None ``errors`` / ``warnings`` must NOT appear on success-only wire payload."""

    async def fake_execute(
        request: SearchSkillRequest, settings: AppSettings
    ) -> SearchSkillResponse:
        return SearchSkillResponse(
            values=[
                SearchSkillOutputRecord(
                    recordId="1",
                    data=SearchSkillOutputData(embedding=[0.5]),
                )
            ]
        )

    _patch_route_deps(monkeypatch, fake_execute)
    req = _make_req(_wire_request(("1", "hello")))

    resp = await search_skill(req)

    payload = json.loads(resp.get_body())
    record = payload["values"][0]
    assert "errors" not in record
    assert "warnings" not in record


@pytest.mark.asyncio
async def test_response_round_trips_back_to_search_skill_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hard Rule #15 receipt: route serializes a typed model -> wire bytes parse back to same model."""

    async def fake_execute(
        request: SearchSkillRequest, settings: AppSettings
    ) -> SearchSkillResponse:
        return SearchSkillResponse(
            values=[
                SearchSkillOutputRecord(
                    recordId="rt",
                    data=SearchSkillOutputData(embedding=[0.9, 1.0]),
                )
            ]
        )

    _patch_route_deps(monkeypatch, fake_execute)
    req = _make_req(_wire_request(("rt", "hello")))

    resp = await search_skill(req)

    round_trip = SearchSkillResponse.model_validate_json(resp.get_body())
    assert round_trip.values[0].record_id == "rt"
    assert round_trip.values[0].data.embedding == [0.9, 1.0]


@pytest.mark.asyncio
async def test_empty_body_returns_422_validation_error() -> None:
    req = _make_req(b"")
    resp = await search_skill(req)
    assert resp.status_code == 422
    payload = json.loads(resp.get_body())
    assert payload["error"] == "validation_error"
    assert isinstance(payload["details"], list) and payload["details"]


@pytest.mark.asyncio
async def test_malformed_json_returns_422() -> None:
    req = _make_req(b"{ not json")
    resp = await search_skill(req)
    assert resp.status_code == 422
    assert json.loads(resp.get_body())["error"] == "validation_error"


@pytest.mark.asyncio
async def test_missing_values_field_returns_422() -> None:
    req = _make_req(json.dumps({}).encode())
    resp = await search_skill(req)
    assert resp.status_code == 422
    payload = json.loads(resp.get_body())
    assert payload["error"] == "validation_error"


@pytest.mark.asyncio
async def test_empty_values_array_returns_422() -> None:
    """``SearchSkillRequest.values`` has ``min_length=1`` (U10a)."""
    req = _make_req(json.dumps({"values": []}).encode())
    resp = await search_skill(req)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_extra_top_level_field_returns_422_due_to_extra_forbid() -> None:
    req = _make_req(
        json.dumps(
            {
                "values": [{"recordId": "1", "data": {"text": "hi"}}],
                "evil": "extra",
            }
        ).encode()
    )
    resp = await search_skill(req)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_azure_error_returns_502_and_logs(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    async def fake_execute(
        request: SearchSkillRequest, settings: AppSettings
    ) -> SearchSkillResponse:
        raise AzureError("upstream embedding boom")

    _patch_route_deps(monkeypatch, fake_execute)
    caplog.set_level(logging.ERROR, logger="functions.core.exception_mapping")
    req = _make_req(_wire_request(("1", "hello")))

    resp = await search_skill(req)

    assert resp.status_code == 502
    assert json.loads(resp.get_body()) == {"error": "upstream_storage_error"}
    record = next(
        r for r in caplog.records if r.message == "search_skill storage call failed"
    )
    assert record.operation == "search_skill"  # type: ignore[attr-defined]
    assert record.trigger == "http"  # type: ignore[attr-defined]
    assert record.status_code == 502  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_unexpected_exception_returns_500_safety_net(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    async def fake_execute(
        request: SearchSkillRequest, settings: AppSettings
    ) -> SearchSkillResponse:
        raise RuntimeError("totally unexpected")

    _patch_route_deps(monkeypatch, fake_execute)
    caplog.set_level(logging.ERROR, logger="functions.core.exception_mapping")
    req = _make_req(_wire_request(("1", "hello")))

    resp = await search_skill(req)

    assert resp.status_code == 500
    assert json.loads(resp.get_body()) == {"error": "internal_server_error"}
    record = next(
        r for r in caplog.records if r.message == "search_skill handler failed"
    )
    assert record.status_code == 500  # type: ignore[attr-defined]


def test_search_skill_route_registered_on_app() -> None:
    # Importing function_app must register the blueprint route.
    function_names = {fb._function._name for fb in app._function_builders}  # type: ignore[attr-defined]
    assert "search_skill" in function_names
    # Regression: every previously registered Phase 6 route still present.
    assert "batch_start" in function_names
    assert "batch_push" in function_names
    assert "add_url" in function_names
    assert "health" in function_names
