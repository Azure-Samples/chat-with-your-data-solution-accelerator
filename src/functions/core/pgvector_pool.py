"""Functions-runtime cache for the pgvector ingestion asyncpg pool.

Functions ingestion blueprints (``batch_push``, ``add_url``,
``search_skill``) share a single ``asyncpg.Pool`` per worker process
via this helper. Mirrors the pool-creation half of
:class:`backend.core.providers.databases.postgres.PostgresClient`
-- the AAD-async-password-provider pattern, the single-flight init
lock, the lifespan-style log-loud-and-reraise failure policy -- but
deliberately omits the chat-history schema bootstrap: Functions only
write to the pgvector ``documents`` table, never to ``conversations``
/ ``messages`` / ``agents`` / ``runtime_config`` / ``admin_audit``.

Lifecycle: hand the resolved ``asyncpg.Pool`` to
:class:`backend.core.providers.search.pgvector.PgVector` so the
provider's ``merge_or_upload_documents`` keeps owning the SQL
boundary -- this helper only owns the *connection* boundary.
"""

import asyncio
import logging

import asyncpg  # pyright: ignore[reportMissingTypeStubs]
from azure.core.credentials_async import AsyncTokenCredential

from backend.core.settings import AppSettings
from backend.core.types import AadScope


logger = logging.getLogger(__name__)


class PgVectorPool:
    def __init__(
        self,
        settings: AppSettings,
        credential: AsyncTokenCredential,
        *,
        pool: asyncpg.Pool | None = None,
    ) -> None:
        self._settings = settings
        self._credential = credential
        # Allow tests + alternate wiring (e.g. a shared pool from the
        # backend lifespan, if a future seam exposes one) to inject a
        # pool. Production path constructs lazily on first acquire().
        self._pool: asyncpg.Pool | None = pool
        # Single lock guards lazy pool construction so two concurrent
        # first-use callers cannot both pass the `is None` check and
        # both call `asyncpg.create_pool`, leaking one pool.
        self._init_lock = asyncio.Lock()

    async def _password_provider(self) -> str:
        token = await self._credential.get_token(AadScope.POSTGRES_FLEX)
        return token.token

    async def acquire(self) -> asyncpg.Pool:
        # Fast path: pool already built.
        if self._pool is not None:
            return self._pool
        async with self._init_lock:
            if self._pool is not None:
                return self._pool
            cfg = self._settings.database
            endpoint = cfg.postgres_endpoint
            if not endpoint:
                raise RuntimeError(
                    "AZURE_POSTGRES_ENDPOINT is not set. PgVectorPool "
                    "requires a libpq URI from the Bicep deployment."
                )
            user = cfg.postgres_admin_principal_name
            if not user:
                raise RuntimeError(
                    "AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME is not set. "
                    "PgVectorPool requires the Entra principal name "
                    "to connect as."
                )
            try:
                new_pool: asyncpg.Pool = (
                    await asyncpg.create_pool(  # pyright: ignore[reportUnknownMemberType]
                        dsn=endpoint,
                        user=user,
                        password=self._password_provider,
                        min_size=1,
                        max_size=10,
                    )
                )
            except (asyncpg.PostgresError, OSError):
                # Lifespan-style policy: log loud + re-raise. The
                # Functions host's retry/poison policy is the recovery
                # path. Endpoint host is logged (not the full DSN) so
                # credentials/tokens never reach the log.
                logger.exception(
                    "asyncpg pool creation failed",
                    extra={
                        "operation": "create_pool",
                        "provider": "pgvector_pool",
                        "endpoint": endpoint,
                    },
                )
                raise
            self._pool = new_pool
            return new_pool

    async def aclose(self) -> None:
        if self._pool is None:
            return
        try:
            await self._pool.close()
        except (asyncpg.PostgresError, OSError):
            # Shutdown is best-effort: the worker is going away
            # regardless. Log at WARNING so the failure is visible
            # without crashing the shutdown sequence.
            logger.warning(
                "asyncpg pool close failed",
                extra={
                    "operation": "aclose",
                    "provider": "pgvector_pool",
                },
            )
        self._pool = None
