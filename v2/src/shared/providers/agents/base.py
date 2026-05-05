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

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from azure.ai.agents.aio import AgentsClient
    from azure.core.credentials_async import AsyncTokenCredential

    from shared.settings import AppSettings


class BaseAgentsProvider(ABC):
    def __init__(
        self,
        settings: "AppSettings",
        credential: "AsyncTokenCredential",
    ) -> None:
        self._settings = settings
        self._credential = credential

    @abstractmethod
    def get_client(self) -> "AgentsClient":
        """Return the (lazily-constructed, cached) `AgentsClient`."""

    @abstractmethod
    async def aclose(self) -> None:
        """Close the underlying SDK transport. Idempotent."""
