"""Tests for the Functions-runtime pgvector pool helper."""

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import asyncpg  # pyright: ignore[reportMissingTypeStubs]
import pytest

from backend.core.settings import AppSettings, DatabaseSettings
from functions.core.pgvector_pool import PgVectorPool

_PGVECTOR_POOL_LOGGER_NAME = "functions.core.pgvector_pool"


def _make_settings(
    *,
    endpoint: str = "postgresql://host:5432/cwyd?sslmode=require",
    user: str = "id-cwyd001",
) -> AppSettings:
    s = MagicMock(spec=AppSettings)
    s.database = DatabaseSettings(
        db_type="postgresql",
        index_store="pgvector",
        postgres_endpoint=endpoint,
        postgres_admin_principal_name=user,
    )
    return s


def _make_settings_with_mock_db(
    *,
    endpoint: str = "",
    user: str = "",
) -> AppSettings:
    # The Pydantic DatabaseSettings model has cross-field validators that
    # reject empty `postgres_endpoint` / `postgres_admin_principal_name`
    # when `db_type="postgresql"`. Tests that exercise the helper's own
    # "endpoint missing" / "principal missing" RuntimeErrors need to bypass
    # those validators -- mock the database attribute directly so the
    # helper sees an empty string at runtime.
    s = MagicMock(spec=AppSettings)
    db = MagicMock()
    db.postgres_endpoint = endpoint
    db.postgres_admin_principal_name = user
    s.database = db
    return s


@pytest.mark.asyncio
async def test_acquire_returns_injected_pool_without_creating_a_new_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentinel_pool = MagicMock()
    create_pool = AsyncMock()
    monkeypatch.setattr(asyncpg, "create_pool", create_pool)
    helper = PgVectorPool(
        settings=_make_settings(),
        credential=AsyncMock(),
        pool=sentinel_pool,
    )

    result = await helper.acquire()

    assert result is sentinel_pool
    create_pool.assert_not_called()


@pytest.mark.asyncio
async def test_acquire_lazily_creates_pool_with_dsn_user_and_password_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created: MagicMock = MagicMock()
    create_pool = AsyncMock(return_value=created)
    monkeypatch.setattr(asyncpg, "create_pool", create_pool)
    helper = PgVectorPool(settings=_make_settings(), credential=AsyncMock())

    result = await helper.acquire()

    assert result is created
    create_pool.assert_awaited_once()
    kwargs = create_pool.await_args.kwargs
    assert kwargs["dsn"] == "postgresql://host:5432/cwyd?sslmode=require"
    assert kwargs["user"] == "id-cwyd001"
    assert kwargs["min_size"] == 1
    assert kwargs["max_size"] == 10
    # `password` is an async callable -- assert behavior, not identity.
    password_cb: Any = kwargs["password"]
    assert callable(password_cb)


@pytest.mark.asyncio
async def test_acquire_caches_pool_across_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_pool = AsyncMock(return_value=MagicMock())
    monkeypatch.setattr(asyncpg, "create_pool", create_pool)
    helper = PgVectorPool(settings=_make_settings(), credential=AsyncMock())

    first = await helper.acquire()
    second = await helper.acquire()

    assert first is second
    assert create_pool.await_count == 1


@pytest.mark.asyncio
async def test_acquire_serializes_concurrent_first_use_callers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two coroutines hitting acquire() at the same time on a cold
    helper must NOT both call asyncpg.create_pool -- the single-flight
    init lock guards against leaking a pool.
    """
    start_event = asyncio.Event()
    finish_event = asyncio.Event()

    async def slow_create(**_: Any) -> MagicMock:
        start_event.set()
        await finish_event.wait()
        return MagicMock()

    create_pool = AsyncMock(side_effect=slow_create)
    monkeypatch.setattr(asyncpg, "create_pool", create_pool)
    helper = PgVectorPool(settings=_make_settings(), credential=AsyncMock())

    task_a = asyncio.create_task(helper.acquire())
    task_b = asyncio.create_task(helper.acquire())
    # Wait until the first create_pool call is in flight, then release.
    await start_event.wait()
    finish_event.set()
    result_a, result_b = await asyncio.gather(task_a, task_b)

    assert result_a is result_b
    assert create_pool.await_count == 1


@pytest.mark.asyncio
async def test_acquire_raises_when_endpoint_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_pool = AsyncMock()
    monkeypatch.setattr(asyncpg, "create_pool", create_pool)
    helper = PgVectorPool(
        settings=_make_settings_with_mock_db(endpoint="", user="id-cwyd001"),
        credential=AsyncMock(),
    )

    with pytest.raises(RuntimeError, match="ENDPOINT"):
        await helper.acquire()
    create_pool.assert_not_called()


@pytest.mark.asyncio
async def test_acquire_raises_when_principal_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_pool = AsyncMock()
    monkeypatch.setattr(asyncpg, "create_pool", create_pool)
    helper = PgVectorPool(
        settings=_make_settings_with_mock_db(
            endpoint="postgresql://host:5432/cwyd?sslmode=require",
            user="",
        ),
        credential=AsyncMock(),
    )

    with pytest.raises(RuntimeError, match="PRINCIPAL"):
        await helper.acquire()
    create_pool.assert_not_called()


@pytest.mark.asyncio
async def test_acquire_logs_and_reraises_on_create_pool_failure(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    create_pool = AsyncMock(side_effect=asyncpg.PostgresError("AAD token rejected"))
    monkeypatch.setattr(asyncpg, "create_pool", create_pool)
    helper = PgVectorPool(settings=_make_settings(), credential=AsyncMock())

    with caplog.at_level("ERROR", logger=_PGVECTOR_POOL_LOGGER_NAME):
        with pytest.raises(asyncpg.PostgresError):
            await helper.acquire()

    matches = [
        r
        for r in caplog.records
        if r.levelname == "ERROR"
        and getattr(r, "operation", None) == "create_pool"
        and getattr(r, "provider", None) == "pgvector_pool"
    ]
    assert len(matches) == 1
    # Endpoint is logged (host only -- a libpq DSN, not a full URL with
    # credentials).
    assert getattr(matches[0], "endpoint", None) == (
        "postgresql://host:5432/cwyd?sslmode=require"
    )


@pytest.mark.asyncio
async def test_password_provider_returns_aad_token_string() -> None:
    credential = AsyncMock()
    credential.get_token = AsyncMock(return_value=MagicMock(token="ya29.fake"))
    helper = PgVectorPool(settings=_make_settings(), credential=credential)

    token = await helper._password_provider()

    assert token == "ya29.fake"
    credential.get_token.assert_awaited_once()


@pytest.mark.asyncio
async def test_aclose_is_noop_when_pool_never_created() -> None:
    helper = PgVectorPool(settings=_make_settings(), credential=AsyncMock())
    # Should not raise.
    await helper.aclose()


@pytest.mark.asyncio
async def test_aclose_closes_pool_and_clears_cache() -> None:
    pool = MagicMock()
    pool.close = AsyncMock()
    helper = PgVectorPool(settings=_make_settings(), credential=AsyncMock(), pool=pool)

    await helper.aclose()

    pool.close.assert_awaited_once()
    # Cache cleared so a subsequent acquire() would rebuild.
    assert helper._pool is None  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_aclose_swallows_close_failure_and_warns(
    caplog: pytest.LogCaptureFixture,
) -> None:
    pool = MagicMock()
    pool.close = AsyncMock(side_effect=asyncpg.PostgresError("socket already closed"))
    helper = PgVectorPool(settings=_make_settings(), credential=AsyncMock(), pool=pool)

    with caplog.at_level("WARNING", logger=_PGVECTOR_POOL_LOGGER_NAME):
        await helper.aclose()  # MUST NOT raise

    matches = [
        r
        for r in caplog.records
        if r.levelname == "WARNING"
        and getattr(r, "operation", None) == "aclose"
        and getattr(r, "provider", None) == "pgvector_pool"
    ]
    assert len(matches) == 1
    # Cache still cleared even though close() failed.
    assert helper._pool is None  # type: ignore[attr-defined]
