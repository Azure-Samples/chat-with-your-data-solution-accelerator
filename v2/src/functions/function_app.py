"""Pillar: Stable Core
Phase: 1 (Infrastructure + Project Skeleton, debt #7)

Modular RAG indexing pipeline host. The full Phase 6 blueprint set
(``batch_start``, ``batch_push``, ``add_url``, ``search_skill``) lands
later — see [v2/docs/development_plan.md] §4 Phase 6, tasks #39–#43.

This stub exposes a single anonymous health endpoint so the container
starts cleanly and ``azd up`` succeeds for the Functions app at the end
of Phase 1.
"""
from __future__ import annotations

import json

import azure.functions as func

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


def _health_payload() -> dict[str, str]:
    """Return the JSON body served by the ``health`` route.

    Extracted so unit tests can assert payload shape without invoking the
    Azure Functions host or building a fake ``HttpRequest``.
    """
    return {"status": "ok"}


@app.function_name(name="health")
@app.route(route="health", methods=["GET"])
def health(req: func.HttpRequest) -> func.HttpResponse:
    """GET /api/health — liveness probe for the Functions container."""
    return func.HttpResponse(
        body=json.dumps(_health_payload()),
        status_code=200,
        mimetype="application/json",
    )
