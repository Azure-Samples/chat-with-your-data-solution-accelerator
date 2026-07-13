"""HTTP response helpers and error discriminator enum for Functions blueprints.

Functions-only helper module that owns:

* :class:`ErrorType` -- the closed set of error-discriminator strings
  blueprints write into the ``{"error": ...}`` JSON body. Defined as
  ``StrEnum`` per Hard Rule #11 so the values double as bare strings on
  the wire while still being a typed, exhaustive set callers can
  pattern-match on.
* :func:`json_response` -- the one place that builds a
  ``func.HttpResponse`` with ``mimetype="application/json"`` and a
  JSON-encoded body, so wire format stays consistent across all
  blueprints and exception paths.
* :class:`ErrorEnvelope` -- the frozen model whose
  ``model_dump(exclude_none=True)`` output is the ``{"error": ...}`` /
  ``{"error": ..., "details": [...]}`` JSON body emitted by the
  Functions HTTP exception mapper.

HTTP status codes come from the stdlib :class:`http.HTTPStatus`
``IntEnum`` -- callers reference ``HTTPStatus.OK``,
``HTTPStatus.UNPROCESSABLE_ENTITY``, ``HTTPStatus.INTERNAL_SERVER_ERROR``,
``HTTPStatus.BAD_GATEWAY`` directly. No local int aliases (the stdlib
already provides the canonical, named, typed set).

Lives under ``functions/core/`` because every consumer is an
``azure.functions`` blueprint -- the backend FastAPI app never
constructs ``func.HttpResponse`` -- per
[.github/instructions/v2-functions-core.instructions.md] "Functions-
runtime helper" rule.
"""

import json
from enum import StrEnum
from http import HTTPStatus
from typing import Any, Final

import azure.functions as func
from pydantic import BaseModel, ConfigDict

_JSON_MIMETYPE: Final[str] = "application/json"


class ErrorType(StrEnum):
    """Discriminator strings emitted in ``{"error": ...}`` JSON bodies."""

    VALIDATION_ERROR = "validation_error"
    UPSTREAM_STORAGE_ERROR = "upstream_storage_error"
    INTERNAL_SERVER_ERROR = "internal_server_error"


class ErrorEnvelope(BaseModel):
    """JSON error body emitted by the Functions HTTP exception mapper."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    error: ErrorType
    details: list[dict[str, Any]] | None = (
        None  # errors() boundary shape, per Hard Rule #15(a)
    )


def json_response(
    payload: dict[str, object], status_code: HTTPStatus
) -> func.HttpResponse:
    """Build a ``func.HttpResponse`` with a JSON body.

    Single source of truth for blueprint response shaping: every
    success and every mapped exception goes through here so the wire
    format (``Content-Type: application/json`` + ``json.dumps`` body
    + correct status code) is identical across the four blueprints.
    """
    return func.HttpResponse(
        body=json.dumps(payload),
        status_code=int(status_code),
        mimetype=_JSON_MIMETYPE,
    )
