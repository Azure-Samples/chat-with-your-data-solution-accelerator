"""Foundry-backed agents provider.

Pillar: Stable Core
Phase: 4

Wraps `azure.ai.projects.aio.AIProjectClient` against the typed Foundry
project endpoint (`AppSettings.foundry.project_endpoint`). Owns the
hosted-agent control-plane surface -- create-if-missing for named
agents (`BaseAgentsProvider.get_or_create_agent`), consumed by the
conversation router bootstrap (`CWYD_AGENT`) and the RAI tool
(`RAI_AGENT`). It also owns the runtime-agent construction seam
(`build_agent`): after resolving the named Prompt Agent it composes an
open-source `agent_framework.Agent` over an
`agent_framework_foundry.FoundryChatClient` bound to the same Foundry
project endpoint and the agent's own model deployment. The orchestrator
and the RAI tool consume the returned `Agent`; this provider owns its
construction so the get-or-create path and the runtime path stay DRY.

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
from collections.abc import Sequence
from typing import Callable

from agent_framework import Agent, ToolTypes
# Debt (dev_plan §0.1 B-IMPL-FOUNDRY-STUBS-DEBT): the OSS
# `agent_framework_foundry` PyPI distribution ships no `py.typed`
# marker, so pyright cannot find stubs even though the package is
# installed and importable. Suppress at the SDK boundary per Hard Rule
# #11(a); clears when the SDK ships a `py.typed` marker or when we
# vendor a minimal local stub.
from agent_framework_foundry import FoundryChatClient  # pyright: ignore[reportMissingTypeStubs]
from azure.ai.projects.aio import AIProjectClient
from azure.core.credentials_async import AsyncTokenCredential
from azure.core.exceptions import AzureError

from backend.core.agents.definitions import AgentDefinition
from backend.core.providers.databases.base import BaseDatabaseClient
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
        client: AIProjectClient | None = None,
        runtime_overrides_getter: Callable[[], RuntimeConfig | None] | None = None,
    ) -> None:
        super().__init__(
            settings,
            credential,
            runtime_overrides_getter=runtime_overrides_getter,
        )
        # Allow tests to inject a fake AIProjectClient. Production path
        # constructs lazily so we don't open an HTTP session at import.
        self._client_override = client
        self._client: AIProjectClient | None = client

    def get_client(self) -> AIProjectClient:
        if self._client is not None:
            return self._client
        endpoint = self._settings.foundry.project_endpoint
        if not endpoint:
            raise RuntimeError(
                "AZURE_AI_PROJECT_ENDPOINT is not set. "
                "FoundryAgentsProvider requires a Foundry project "
                "endpoint to construct AIProjectClient."
            )
        self._client = AIProjectClient(
            endpoint=endpoint, credential=self._credential
        )
        return self._client

    async def build_agent(
        self,
        definition: AgentDefinition,
        db: BaseDatabaseClient,
        *,
        extra_tools: Sequence[ToolTypes] | None = None,
    ) -> Agent:
        """Resolve `definition` to a runtime `agent_framework.Agent`.

        Single construction seam shared by every caller that needs to
        *invoke* a Foundry-hosted agent (the `agent_framework`
        orchestrator for `CWYD_AGENT`, the RAI tool for `RAI_AGENT`).
        The named Prompt Agent is resolved / created server-side via
        `get_or_create_agent` (so the agent and its baked-in tools are
        addressable by name and visible in the Foundry portal), then a
        client-side `Agent` is composed over a `FoundryChatClient` bound
        to the same project endpoint and the agent's own model
        deployment. Keeping invocation client-side -- rather than the
        by-name `FoundryAgent` Responses path -- is what lets
        multi-agent orchestration (Magentic / hand-off) drive the same
        object.

        `extra_tools` are runtime tool objects the caller attaches to
        the client-side agent (e.g. the Knowledge Base retrieval tool
        the orchestrator builds per request); they are additive to any
        tools already baked into the server-side definition.
        """
        name = await self.get_or_create_agent(definition, db)
        resolved = self._resolve_definition(definition)
        deployment = self._settings.openai.gpt_deployment
        tools = list(extra_tools) if extra_tools else None
        try:
            chat_client = FoundryChatClient(
                project_endpoint=self._settings.foundry.project_endpoint,
                model=deployment,
                credential=self._credential,
            )
            return Agent(
                client=chat_client,
                name=name,
                instructions=resolved.instructions,
                description=resolved.description,
                tools=tools,
            )
        except AzureError:
            # FoundryChatClient / Agent construction crossed the SDK
            # boundary and failed (auth, transport). Surface it so the
            # caller maps it to a sanitized 503 -- never a half-built
            # agent.
            logger.exception(
                "foundry agents build_agent failed",
                extra={
                    "operation": "build_agent",
                    "provider": "foundry_agents",
                    "agent_name": definition.name,
                    "deployment": deployment,
                },
            )
            raise

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
