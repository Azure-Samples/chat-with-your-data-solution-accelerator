"""Pillar: Stable Core / Phase: 6 — tests for functions/core/exception_mapping.py."""

import json
import logging
from http import HTTPStatus

import azure.functions as func
import pytest
from azure.core.exceptions import AzureError
from pydantic import BaseModel, ValidationError

from functions.core.exception_mapping import (
    log_queue_errors,
    map_function_exceptions,
)


class _SampleBody(BaseModel):
    name: str


def _force_validation_error() -> ValidationError:
    try:
        _SampleBody.model_validate({})
    except ValidationError as exc:
        return exc
    raise AssertionError("expected ValidationError")


@pytest.mark.asyncio
async def test_decorator_returns_handler_response_when_no_exception() -> None:
    @map_function_exceptions("batch_start")
    async def route(_req: func.HttpRequest) -> func.HttpResponse:
        return func.HttpResponse(body=b"{}", status_code=200, mimetype="application/json")

    resp = await route(func.HttpRequest(method="POST", url="/", body=b""))
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_decorator_maps_validation_error_to_422_with_details() -> None:
    exc = _force_validation_error()

    @map_function_exceptions("batch_start")
    async def route(_req: func.HttpRequest) -> func.HttpResponse:
        raise exc

    resp = await route(func.HttpRequest(method="POST", url="/", body=b""))
    assert resp.status_code == int(HTTPStatus.UNPROCESSABLE_ENTITY)
    body = json.loads(resp.get_body())
    assert body["error"] == "validation_error"
    assert isinstance(body["details"], list)
    assert body["details"][0]["loc"] == ["name"]
    # input field is excluded per include_input=False to avoid leaking raw bodies.
    assert "input" not in body["details"][0]


@pytest.mark.asyncio
async def test_decorator_maps_azure_error_to_502() -> None:
    @map_function_exceptions("batch_start")
    async def route(_req: func.HttpRequest) -> func.HttpResponse:
        raise AzureError("blob 503")

    resp = await route(func.HttpRequest(method="POST", url="/", body=b""))
    assert resp.status_code == int(HTTPStatus.BAD_GATEWAY)
    assert json.loads(resp.get_body()) == {"error": "upstream_storage_error"}


@pytest.mark.asyncio
async def test_decorator_maps_unexpected_exception_to_500() -> None:
    @map_function_exceptions("batch_start")
    async def route(_req: func.HttpRequest) -> func.HttpResponse:
        raise RuntimeError("boom")

    resp = await route(func.HttpRequest(method="POST", url="/", body=b""))
    assert resp.status_code == int(HTTPStatus.INTERNAL_SERVER_ERROR)
    assert json.loads(resp.get_body()) == {"error": "internal_server_error"}


@pytest.mark.asyncio
async def test_validation_error_logs_warning_not_exception(
    caplog: pytest.LogCaptureFixture,
) -> None:
    exc = _force_validation_error()

    @map_function_exceptions("batch_start")
    async def route(_req: func.HttpRequest) -> func.HttpResponse:
        raise exc

    with caplog.at_level(logging.WARNING, logger="functions.core.exception_mapping"):
        await route(func.HttpRequest(method="POST", url="/", body=b""))

    records = [r for r in caplog.records if r.name == "functions.core.exception_mapping"]
    assert len(records) == 1
    record = records[0]
    assert record.levelno == logging.WARNING
    # logger.warning does NOT attach exception info; logger.exception would.
    assert record.exc_info is None
    assert record.operation == "batch_start"  # type: ignore[attr-defined]
    assert record.trigger == "http"  # type: ignore[attr-defined]
    assert record.status_code == 422  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_azure_error_logs_exception_with_structured_extras(
    caplog: pytest.LogCaptureFixture,
) -> None:
    @map_function_exceptions("batch_start")
    async def route(_req: func.HttpRequest) -> func.HttpResponse:
        raise AzureError("blob 503")

    with caplog.at_level(logging.ERROR, logger="functions.core.exception_mapping"):
        await route(func.HttpRequest(method="POST", url="/", body=b""))

    records = [r for r in caplog.records if r.name == "functions.core.exception_mapping"]
    assert len(records) == 1
    record = records[0]
    assert record.levelno == logging.ERROR
    assert record.exc_info is not None  # logger.exception attaches traceback
    assert record.operation == "batch_start"  # type: ignore[attr-defined]
    assert record.trigger == "http"  # type: ignore[attr-defined]
    assert record.status_code == 502  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_unexpected_exception_logs_exception_with_500_status(
    caplog: pytest.LogCaptureFixture,
) -> None:
    @map_function_exceptions("batch_start")
    async def route(_req: func.HttpRequest) -> func.HttpResponse:
        raise RuntimeError("boom")

    with caplog.at_level(logging.ERROR, logger="functions.core.exception_mapping"):
        await route(func.HttpRequest(method="POST", url="/", body=b""))

    records = [r for r in caplog.records if r.name == "functions.core.exception_mapping"]
    assert len(records) == 1
    record = records[0]
    assert record.levelno == logging.ERROR
    assert record.exc_info is not None
    assert record.status_code == 500  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_decorator_accepts_custom_trigger_kind() -> None:
    @map_function_exceptions("dead_letter", trigger="queue")
    async def handler() -> func.HttpResponse:
        raise AzureError("queue down")

    resp = await handler()
    assert resp.status_code == int(HTTPStatus.BAD_GATEWAY)


@pytest.mark.asyncio
async def test_decorator_preserves_handler_name_and_doc() -> None:
    @map_function_exceptions("batch_start")
    async def my_route(_req: func.HttpRequest) -> func.HttpResponse:
        """Original docstring."""
        return func.HttpResponse(status_code=200)

    assert my_route.__name__ == "my_route"
    assert my_route.__doc__ == "Original docstring."


# ---------------------------------------------------------------------------
# log_queue_errors -- queue-trigger sibling of map_function_exceptions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_queue_decorator_passthrough_returns_none_and_logs_nothing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    @log_queue_errors("batch_push")
    async def handler(_msg: object) -> None:
        return None

    with caplog.at_level(logging.DEBUG, logger="functions.core.exception_mapping"):
        result = await handler("ok")

    assert result is None
    assert not [r for r in caplog.records if r.name == "functions.core.exception_mapping"]


@pytest.mark.asyncio
async def test_queue_decorator_validation_error_reraises_with_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    exc = _force_validation_error()

    @log_queue_errors("batch_push")
    async def handler(_msg: object) -> None:
        raise exc

    with caplog.at_level(logging.WARNING, logger="functions.core.exception_mapping"):
        with pytest.raises(ValidationError):
            await handler("drifted")

    records = [r for r in caplog.records if r.name == "functions.core.exception_mapping"]
    assert len(records) == 1
    record = records[0]
    assert record.levelno == logging.WARNING
    # logger.warning does NOT attach exception info; logger.exception would.
    assert record.exc_info is None
    assert record.operation == "batch_push"  # type: ignore[attr-defined]
    assert record.trigger == "queue"  # type: ignore[attr-defined]
    # Queue decorator has no wire status code -- field intentionally absent.
    assert not hasattr(record, "status_code")


@pytest.mark.asyncio
async def test_queue_decorator_azure_error_reraises_with_exception(
    caplog: pytest.LogCaptureFixture,
) -> None:
    @log_queue_errors("batch_push")
    async def handler(_msg: object) -> None:
        raise AzureError("blob 503")

    with caplog.at_level(logging.ERROR, logger="functions.core.exception_mapping"):
        with pytest.raises(AzureError):
            await handler("msg")

    records = [r for r in caplog.records if r.name == "functions.core.exception_mapping"]
    assert len(records) == 1
    record = records[0]
    assert record.levelno == logging.ERROR
    assert record.exc_info is not None  # logger.exception attaches traceback
    assert record.operation == "batch_push"  # type: ignore[attr-defined]
    assert record.trigger == "queue"  # type: ignore[attr-defined]
    assert not hasattr(record, "status_code")


@pytest.mark.asyncio
async def test_queue_decorator_unexpected_exception_reraises_with_exception(
    caplog: pytest.LogCaptureFixture,
) -> None:
    @log_queue_errors("batch_push")
    async def handler(_msg: object) -> None:
        raise RuntimeError("boom")

    with caplog.at_level(logging.ERROR, logger="functions.core.exception_mapping"):
        with pytest.raises(RuntimeError):
            await handler("msg")

    records = [r for r in caplog.records if r.name == "functions.core.exception_mapping"]
    assert len(records) == 1
    record = records[0]
    assert record.levelno == logging.ERROR
    assert record.exc_info is not None
    assert record.operation == "batch_push"  # type: ignore[attr-defined]
    assert record.trigger == "queue"  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_queue_decorator_preserves_handler_name_and_doc() -> None:
    @log_queue_errors("batch_push")
    async def my_consumer(_msg: object) -> None:
        """Original docstring."""
        return None

    assert my_consumer.__name__ == "my_consumer"
    assert my_consumer.__doc__ == "Original docstring."

