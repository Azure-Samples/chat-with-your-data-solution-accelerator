"""Modular RAG indexing pipeline host. Registers the ingestion
blueprint set: :mod:`functions.batch_start`, :mod:`functions.batch_push`,
:mod:`functions.add_url`, :mod:`functions.blob_event`, and
:mod:`functions.search_skill`.

Also exposes a single anonymous ``health`` endpoint so the container
starts cleanly and ``azd up`` succeeds for the Functions app.
"""

import azure.functions as func
from pydantic import BaseModel, ConfigDict

from functions.add_url.blueprint import bp as add_url_bp
from functions.batch_push.blueprint import bp as batch_push_bp
from functions.batch_start.blueprint import bp as batch_start_bp
from functions.blob_event.blueprint import bp as blob_event_bp
from functions.core.telemetry import configure_telemetry
from functions.search_skill.blueprint import bp as search_skill_bp

# Wire Azure Monitor export before registering functions (no-op when the
# App Insights connection string is absent). Logic lives in
# functions.core.telemetry so this module stays a thin registration surface.
configure_telemetry()

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)
app.register_functions(batch_start_bp)
app.register_functions(batch_push_bp)
app.register_functions(add_url_bp)
app.register_functions(blob_event_bp)
app.register_functions(search_skill_bp)


class HealthPayload(BaseModel):
    """Liveness response body for the ``health`` route.

    Single-field today (``status``) but defined as a model per Hard
    Rule #15 -- closed-set wire shapes must be typed models even at
    arity 1, because that door always becomes "two fields don't
    either." Frozen + ``extra="forbid"`` so a stray field passed at
    construction time fails fast.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: str = "ok"


def _health_payload() -> HealthPayload:
    """Return the JSON body served by the ``health`` route.

    Extracted so unit tests can assert payload shape without invoking the
    Azure Functions host or building a fake ``HttpRequest``.
    """
    return HealthPayload()


@app.function_name(name="health")
@app.route(route="health", methods=["GET"])
def health(req: func.HttpRequest) -> func.HttpResponse:
    """GET /api/health -- liveness probe for the Functions container.

    Method: ``GET`` only.
    Responses:
      * 200 -- ``{"status": "ok"}`` (JSON body serialized from
        :class:`HealthPayload`); returned whenever the host is up.
    """
    return func.HttpResponse(
        body=_health_payload().model_dump_json(),
        status_code=200,
        mimetype="application/json",
    )
