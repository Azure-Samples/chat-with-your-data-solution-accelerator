"""Foundry-backed agents provider.

Pillar: Stable Core
Phase: 4

Wraps `azure.ai.agents.aio.AgentsClient` against the typed Foundry
project endpoint (`AppSettings.foundry.project_endpoint`). The
constructed `AgentsClient` is the same SDK object the
`agent_framework` orchestrator already consumes -- this provider is
just the swap-in seam (Hard Rule #4) and the lifecycle owner.

Construction is lazy: no HTTP session is opened at __init__ time,
so module import stays cheap. The first `get_client()` call builds
the client; subsequent calls return the cached instance.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from azure.ai.agents.aio import AgentsClient

from . import registry
from .base import BaseAgentsProvider

if TYPE_CHECKING:
    from azure.core.credentials_async import AsyncTokenCredential

    from shared.settings import AppSettings


@registry.register("foundry")
class FoundryAgentsProvider(BaseAgentsProvider):
    def __init__(
        self,
        settings: "AppSettings",
        credential: "AsyncTokenCredential",
        *,
        client: "AgentsClient | None" = None,
    ) -> None:
        super().__init__(settings, credential)
        # Allow tests to inject a fake AgentsClient. Production path
        # constructs lazily so we don't open an HTTP session at import.
        self._client_override = client
        self._client: "AgentsClient | None" = client

    def get_client(self) -> "AgentsClient":
        if self._client is not None:
            return self._client
        endpoint = self._settings.foundry.project_endpoint
        if not endpoint:
            raise RuntimeError(
                "AZURE_AI_PROJECT_ENDPOINT is not set. "
                "FoundryAgentsProvider requires a Foundry project "
                "endpoint to construct AgentsClient."
            )
        self._client = AgentsClient(
            endpoint=endpoint, credential=self._credential
        )
        return self._client

    async def aclose(self) -> None:
        # Caller-owned overrides are NOT closed by us -- whoever
        # injected the client owns its lifecycle.
        if self._client is None or self._client is self._client_override:
            self._client = None
            return
        await self._client.close()
        self._client = None
