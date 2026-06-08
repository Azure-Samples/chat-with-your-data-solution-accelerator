"""Foundry-backed agents provider.

Pillar: Stable Core
Phase: 4

Wraps `azure.ai.agents.aio.AgentsClient` against the typed Foundry
project endpoint (`AppSettings.foundry.project_endpoint`). Owns the
hosted-agent control-plane surface only -- create-if-missing for
named agents (`BaseAgentsProvider.get_or_create_agent`), consumed by
the conversation router bootstrap (`CWYD_AGENT`) and the RAI tool
(`RAI_AGENT`). Runtime invocation lives in the orchestrator layer
(`backend.core.providers.orchestrators.agent_framework`) and uses the
open-source `agent_framework_foundry.FoundryAgent` client directly,
not this provider.

Construction is lazy: no HTTP session is opened at __init__ time,
so module import stays cheap. The first `get_client()` call builds
the client; subsequent calls return the cached instance.

Try/except policy:
  * `aclose()` is shutdown best-effort per the policy doc Lifespan
    row -- catches `(AzureError, OSError)`, logs at WARNING with
    structured extras, and clears the cached client so a restart
    rebuilds cleanly. The container is going away regardless; a
    transport drop on the way out must NOT crash the lifespan
    shutdown sequence.
  * The `get_or_create_agent` path lives on the base class; its
    SDK boundaries are wrapped there (see `base.py`).
"""

import logging
from typing import Callable

from azure.ai.agents.aio import AgentsClient
from azure.core.credentials_async import AsyncTokenCredential
from azure.core.exceptions import AzureError

from backend.core.settings import AppSettings
from backend.core.types import RuntimeConfig

from .registry import registry
from .base import BaseAgentsProvider

logger = logging.getLogger(__name__)


@registry.register("foundry")
class FoundryAgentsProvider(BaseAgentsProvider):
    def __init__(
        self,
        settings: AppSettings,
        credential: AsyncTokenCredential,
        *,
        client: AgentsClient | None = None,
        runtime_overrides_getter: Callable[[], RuntimeConfig | None] | None = None,
    ) -> None:
        super().__init__(
            settings,
            credential,
            runtime_overrides_getter=runtime_overrides_getter,
        )
        # Allow tests to inject a fake AgentsClient. Production path
        # constructs lazily so we don't open an HTTP session at import.
        self._client_override = client
        self._client: "AgentsClient | None" = client

    def get_client(self) -> AgentsClient:
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
        try:
            await self._client.close()
        except (AzureError, OSError):
            # Lifespan shutdown is best-effort: the container is
            # going away regardless. Log at WARNING so the failure
            # is visible without crashing the shutdown sequence.
            logger.warning(
                "foundry agents AgentsClient.close failed",
                extra={
                    "operation": "aclose",
                    "provider": "foundry_agents",
                },
            )
        self._client = None
