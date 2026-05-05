"""Agents provider ABC.

Pillar: Stable Core
Phase: 4

Every concrete agents provider (`foundry`, future swap-ins) inherits
from `BaseAgentsProvider` and self-registers via
`@registry.register("<key>")`.

Constructors take `AppSettings` + an `AsyncTokenCredential` (managed
identity in production, AzureCli in local dev) -- never an API key
or connection string with embedded secrets (Hard Rule #2).

Lifecycle: providers may hold an SDK client (`AgentsClient`) that owns
an HTTP transport. Callers invoke `await provider.aclose()` during
shutdown -- the FastAPI lifespan in `backend/app.py` does this for
the cached singleton.

The `get_client()` method intentionally returns the raw SDK type
(`azure.ai.agents.aio.AgentsClient`) rather than wrapping it -- the
`agent_framework` orchestrator already owns the conversation flow
(thread create / run process / messages list) and the SDK shape is
stable. Wrapping would add ceremony without any swap-in benefit
since every provider in this domain ultimately produces the same
SDK type.
"""
from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from azure.core.exceptions import ResourceNotFoundError

if TYPE_CHECKING:
    from azure.ai.agents.aio import AgentsClient
    from azure.core.credentials_async import AsyncTokenCredential

    from shared.agents.definitions import AgentDefinition
    from shared.providers.databases.base import BaseDatabaseClient
    from shared.settings import AppSettings


class BaseAgentsProvider(ABC):
    def __init__(
        self,
        settings: "AppSettings",
        credential: "AsyncTokenCredential",
    ) -> None:
        self._settings = settings
        self._credential = credential
        # Process-local cache of resolved Foundry agent ids, keyed by
        # `AgentDefinition.name`. Populated by `get_or_create_agent` so
        # the steady-state path is a dict lookup -- no DB read, no
        # Foundry round-trip.
        self._agent_cache: dict[str, str] = {}
        # Per-key locks serialize the create path so two concurrent
        # first-requests for the same agent don't double-create
        # (which would orphan one Foundry agent and race on the
        # `db.upsert_agent_id` write). `setdefault` is atomic in
        # CPython for dict ops, so the throwaway `Lock()` on
        # subsequent calls is acceptable -- locks aren't bound to an
        # event loop until first `acquire()` (Python 3.10+).
        self._create_locks: dict[str, asyncio.Lock] = {}

    @abstractmethod
    def get_client(self) -> "AgentsClient":
        """Return the (lazily-constructed, cached) `AgentsClient`."""

    @abstractmethod
    async def aclose(self) -> None:
        """Close the underlying SDK transport. Idempotent."""

    async def get_or_create_agent(
        self,
        definition: "AgentDefinition",
        db: "BaseDatabaseClient",
    ) -> str:
        """Resolve `definition` to a Foundry agent id, creating the
        agent on first call and persisting the id for next time.

        Algorithm:

        1. Process cache hit -> return immediately. This is the
           steady-state path.
        2. DB lookup (`db.get_agent_id`). On hit, validate the
           persisted id by calling `client.get_agent(...)` -- a stale
           id (Foundry-side delete, environment rebuild) is detected
           here and falls through to step 4.
        3. Per-key lock + double-checked cache. Two concurrent first
           callers race past the cache miss; the second one sees the
           winner's value once the lock releases.
        4. `client.create_agent(...)` -> `db.upsert_agent_id(...)` ->
           cache -> return. The Foundry write happens before the DB
           write so a DB failure leaves a recoverable orphan (the
           next request will see the DB miss and create-or-replace),
           rather than a stale id pointing at no Foundry agent.

        Concrete providers implement `get_client()`; this method is
        provider-agnostic (deviation from cleanup_audit prose: the
        algorithm is identical for every Agents-SDK backend, so we
        share it on the base class instead of forcing each provider
        to reimplement the cache + lock + 404-fallthrough plumbing).
        """
        cached = self._agent_cache.get(definition.name)
        if cached is not None:
            return cached

        client = self.get_client()
        deployment = getattr(self._settings.openai, definition.deployment_attr)

        persisted = await db.get_agent_id(definition.name)
        if persisted is not None:
            try:
                await client.get_agent(persisted)
            except ResourceNotFoundError:
                # Stale id -- Foundry agent was deleted out from
                # under us. Fall through to recreate; the upsert
                # in step 4 rewrites the DB row with the new id.
                persisted = None
            else:
                self._agent_cache[definition.name] = persisted
                return persisted

        lock = self._create_locks.setdefault(definition.name, asyncio.Lock())
        async with lock:
            # Double-checked: another coroutine may have raced past
            # the cache miss and created the agent while we were
            # blocked on the lock. Trust the cache, not the DB --
            # the cache write is the last step of the create path,
            # so a cache hit guarantees the DB row exists too.
            cached = self._agent_cache.get(definition.name)
            if cached is not None:
                return cached

            created = await client.create_agent(
                model=deployment,
                name=definition.name,
                description=definition.description,
                instructions=definition.instructions,
                tools=list(definition.tools),
            )
            agent_id = created.id
            await db.upsert_agent_id(definition.name, agent_id)
            self._agent_cache[definition.name] = agent_id
            return agent_id
