"""Exception-to-HTTP mapping decorator for Functions HTTP routes.

Functions-only helper that owns the four-arm exception ladder every
blueprint HTTP route would otherwise repeat inline (a single
``batch_start`` blueprint inlined ~60 lines of try/except). Applying
:func:`map_function_exceptions` reduces each route body to just the
happy-path logic; the decorator owns:

* ``pydantic.ValidationError`` -> HTTP 422 with ``{"error":
  ErrorType.VALIDATION_ERROR, "details": exc.errors(include_input=False)}``
  body and a structured ``logger.warning`` (not ``exception`` --
  validation failures are caller errors, not bugs, per
  [v2/docs/exception_handling_policy.md] "Validation errors").
* ``azure.core.exceptions.AzureError`` -> HTTP 502 with ``{"error":
  ErrorType.UPSTREAM_STORAGE_ERROR}`` and ``logger.exception``.
* Final ``BLE001`` safety-net for any other exception -> HTTP 500 with
  ``{"error": ErrorType.INTERNAL_SERVER_ERROR}`` and
  ``logger.exception``.

All three branches emit structured ``extra={"operation": <route name>,
"trigger": <trigger kind>, "status_code": <int>}`` so log queries can
filter by route + error class without parsing message strings.

Per-request fields like ``container_name`` are intentionally **not**
captured by the decorator (it has no view into route-local state).
Route bodies can still attach their own structured ``logger.info``
calls before the exception bubbles; the decorator is the wire-error
mapping layer, not the only logging layer.

This module also exposes :func:`log_queue_errors` -- the queue-trigger
sibling of :func:`map_function_exceptions`. Queue triggers have a
fundamentally different wire contract (return ``None``, runtime owns
retry / poison-queue), so they get a dedicated decorator instead of a
polymorphic one. See that function's docstring for the contract.

Lives under ``functions/core/`` because it composes only Functions-
runtime types (``func.HttpResponse``, ``ErrorType``, ``HTTPStatus``,
``json_response``) and is consumed exclusively by ``functions/**``
blueprints.
"""

import functools
import logging
from collections.abc import Awaitable, Callable
from http import HTTPStatus
from typing import ParamSpec

import azure.functions as func
from azure.core.exceptions import AzureError
from pydantic import ValidationError

from functions.core.http import ErrorEnvelope, ErrorType, json_response

logger = logging.getLogger(__name__)

_P = ParamSpec("_P")

_HttpHandler = Callable[_P, Awaitable[func.HttpResponse]]
_QueueHandler = Callable[_P, Awaitable[None]]


def map_function_exceptions(
    operation: str,
    *,
    trigger: str = "http",
) -> Callable[[_HttpHandler[_P]], _HttpHandler[_P]]:
    """Wrap an HTTP route in the standard 422/502/500 ladder.

    ``operation`` should be the route name (e.g. ``"batch_start"``) and
    is emitted as the ``operation`` log field on every mapped error.
    ``trigger`` defaults to ``"http"`` -- pass another value (e.g.
    ``"queue"``) if this decorator is later reused on non-HTTP
    triggers, though today only the HTTP blueprints use it.
    """

    def _decorator(fn: _HttpHandler[_P]) -> _HttpHandler[_P]:
        @functools.wraps(fn)
        async def _wrapper(*args: _P.args, **kwargs: _P.kwargs) -> func.HttpResponse:
            try:
                return await fn(*args, **kwargs)
            except ValidationError as exc:
                status = HTTPStatus.UNPROCESSABLE_ENTITY
                logger.warning(
                    "%s request validation failed",
                    operation,
                    extra={
                        "operation": operation,
                        "trigger": trigger,
                        "status_code": int(status),
                    },
                )
                return json_response(
                    ErrorEnvelope(
                        error=ErrorType.VALIDATION_ERROR,
                        details=exc.errors(include_input=False),
                    ).model_dump(exclude_none=True),
                    status,
                )
            except AzureError:
                status = HTTPStatus.BAD_GATEWAY
                logger.exception(
                    "%s storage call failed",
                    operation,
                    extra={
                        "operation": operation,
                        "trigger": trigger,
                        "status_code": int(status),
                    },
                )
                return json_response(
                    ErrorEnvelope(error=ErrorType.UPSTREAM_STORAGE_ERROR).model_dump(
                        exclude_none=True
                    ),
                    status,
                )
            except Exception:  # noqa: BLE001 -- final safety net for HTTP route
                status = HTTPStatus.INTERNAL_SERVER_ERROR
                logger.exception(
                    "%s handler failed",
                    operation,
                    extra={
                        "operation": operation,
                        "trigger": trigger,
                        "status_code": int(status),
                    },
                )
                return json_response(
                    ErrorEnvelope(error=ErrorType.INTERNAL_SERVER_ERROR).model_dump(
                        exclude_none=True
                    ),
                    status,
                )

        return _wrapper

    return _decorator


def log_queue_errors(
    operation: str,
) -> Callable[[_QueueHandler[_P]], _QueueHandler[_P]]:
    """Wrap a queue-trigger handler with structured exception logging.

    Queue triggers are *not* terminal wire endpoints (no HTTP response
    to shape); on uncaught exception the Azure Functions runtime
    applies its configured retry policy and ultimately moves the
    message to the poison queue. This decorator only adds standardized
    observability: every exception is logged with consistent
    ``extra={"operation": <name>, "trigger": "queue"}`` then
    **re-raised** so the runtime's retry / poison-queue semantics
    still engage.

    Branch policy mirrors :func:`map_function_exceptions` per
    [v2/docs/exception_handling_policy.md] "Functions blueprints":

    * ``pydantic.ValidationError`` (drifted envelope from a producer)
      -> ``logger.warning`` -- caller error, not bug, but the warning
      still surfaces a structured trail so an operator can correlate a
      poison run with the original drift.
    * ``azure.core.exceptions.AzureError`` (transient SDK failure on a
      downstream call) -> ``logger.exception`` -- traceback attached.
    * Final ``BLE001`` safety net for any other ``Exception`` ->
      ``logger.exception``.

    All three branches **re-raise**. The decorator is observability-
    only; the runtime owns the retry policy.
    """

    def _decorator(fn: _QueueHandler[_P]) -> _QueueHandler[_P]:
        @functools.wraps(fn)
        async def _wrapper(*args: _P.args, **kwargs: _P.kwargs) -> None:
            try:
                return await fn(*args, **kwargs)
            except ValidationError:
                logger.warning(
                    "%s queue message validation failed",
                    operation,
                    extra={"operation": operation, "trigger": "queue"},
                )
                raise
            except AzureError:
                logger.exception(
                    "%s queue handler storage call failed",
                    operation,
                    extra={"operation": operation, "trigger": "queue"},
                )
                raise
            except Exception:  # noqa: BLE001 -- final safety net for queue handler
                logger.exception(
                    "%s queue handler failed",
                    operation,
                    extra={"operation": operation, "trigger": "queue"},
                )
                raise

        return _wrapper

    return _decorator
