"""Agents provider ABC.

Pillar: Stable Core
Phase: 4

Every concrete agents provider (`foundry`, future swap-ins) inherits
from `BaseAgentsProvider` and self-registers via
`@registry.register("<key>")`.

Constructors take `AppSettings` + an `AsyncTokenCredential` (managed
identity in production, AzureCli in local dev) -- never an API key
or connection string with embedded secrets (Hard Rule #2).

Lifecycle: providers may hold an SDK client (`AIProjectClient`) that
owns an HTTP transport. Callers invoke `await provider.aclose()`
during shutdown -- the FastAPI lifespan in `backend/app.py` does this
for the cached singleton.

The `get_client()` method intentionally returns the raw SDK type
(`azure.ai.projects.aio.AIProjectClient`) rather than wrapping it --
the provisioning path drives the Foundry agent control plane
(`agents.get` / `agents.create_version`) and the orchestrator builds
its chat client from the same project endpoint. Wrapping would add
ceremony without any swap-in benefit since every provider in this
domain ultimately produces the same SDK type.

Try/except policy (Phase C2e -- mirrors C2d for foundry_iq /
azure_search):
  * Per v2/docs/exception_handling_policy.md (Provider entry-points
    row), every `await client.X(...)` against the agents SDK is
    wrapped with `azure.core.exceptions.AzureError` -- the umbrella
    for every azure-core SDK transport / service error
    (`HttpResponseError`, `ServiceRequestError`,
    `ClientAuthenticationError`, etc.). Each wrap logs at ERROR via
    `logger.exception(..., extra={"operation": ..., "provider":
    "agents", "agent_name": ..., "deployment": ...})` and re-raises
    so the lifespan / app-level handler maps it to a sanitized 503.
  * `ResourceNotFoundError` keeps its existing orphan-recovery
    branch (stale persisted id -> fall through to recreate). Because
    `ResourceNotFoundError` is itself an `AzureError` subclass, the
    `except` blocks MUST be ordered with `ResourceNotFoundError`
    first so the more specific 404 path wins -- otherwise every
    environment rebuild would log an ERROR and re-raise instead of
    silently recovering.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Callable

from agent_framework import Agent, ToolTypes
from azure.ai.projects.aio import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition, Tool
from azure.core.credentials_async import AsyncTokenCredential
from azure.core.exceptions import (
    AzureError,
    HttpResponseError,
    ResourceNotFoundError,
)

from backend.core.agents.definitions import (
    CWYD_AGENT,
    AgentDefinition,
    resolve_cwyd_instructions,
)
from backend.core.providers.databases.base import BaseDatabaseClient
from backend.core.settings import AppSettings
from backend.core.types import RuntimeConfig

logger = logging.getLogger(__name__)


# Builders that realize an `AgentDefinition.tools` opaque key as a
# concrete Foundry SDK `Tool` for the server-side prompt-agent
# definition. Empty by default: the built-in agents ground via an MCP
# tool attached client-side at `build_agent` time, so neither declares
# a definition-level tool. A swap-in agent that needs a server-side
# tool registers its builder here, keyed by the string it places in
# `AgentDefinition.tools`.
_DEFINITION_TOOL_BUILDERS: dict[str, Callable[[], Tool]] = {}


def _definition_tools_to_sdk(keys: tuple[str, ...]) -> list[Tool] | None:
    """Resolve `AgentDefinition.tools` keys to Foundry SDK `Tool`s.

    Returns `None` when no keys are declared so the prompt-agent
    definition omits the field. Every key must resolve through
    `_DEFINITION_TOOL_BUILDERS`; an unrecognized key raises rather than
    being handed to the SDK as a bare string, which keeps the value
    entering `PromptAgentDefinition.tools` honestly typed as
    `list[Tool]`.
    """
    if not keys:
        return None
    resolved: list[Tool] = []
    for key in keys:
        builder = _DEFINITION_TOOL_BUILDERS.get(key)
        if builder is None:
            raise ValueError(
                f"Unrecognized agent definition tool key {key!r}; "
                f"registered keys: {sorted(_DEFINITION_TOOL_BUILDERS)}"
            )
        resolved.append(builder())
    return resolved


class BaseAgentsProvider(ABC):
    def __init__(
        self,
        settings: AppSettings,
        credential: AsyncTokenCredential,
        *,
        runtime_overrides_getter: Callable[[], RuntimeConfig | None] | None = None,
    ) -> None:
        self._settings = settings
        self._credential = credential
        # Late-binding handle to the persisted `RuntimeConfig`. The
        # lifespan owns the canonical reference on `app.state` and
        # reassigns it on every successful PATCH; the getter shape
        # keeps the provider decoupled from `app.state` and lets each
        # cold-start create-agent call read the most recent value.
        self._runtime_overrides_getter = runtime_overrides_getter
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
    def get_client(self) -> AIProjectClient:
        """Return the (lazily-constructed, cached) `AIProjectClient`."""

    @abstractmethod
    async def aclose(self) -> None:
        """Close the underlying SDK transport. Idempotent."""

    @abstractmethod
    async def build_agent(
        self,
        definition: AgentDefinition,
        db: BaseDatabaseClient,
        *,
        extra_tools: Sequence[ToolTypes] | None = None,
    ) -> Agent:
        """Resolve `definition` to a runtime `agent_framework.Agent`.

        The single construction seam shared by every caller that needs
        to *invoke* a hosted agent (the `agent_framework` orchestrator
        for `CWYD_AGENT`, the RAI tool for `RAI_AGENT`). The named
        Prompt Agent is resolved / created server-side via
        `get_or_create_agent`, then a client-side `Agent` is composed
        over the provider's chat client bound to the agent's own model
        deployment -- keeping invocation client-side is what lets
        multi-agent orchestration (Magentic / hand-off) drive the same
        object.

        `extra_tools` are runtime tool objects the caller attaches to
        the client-side agent (e.g. the Knowledge Base retrieval tool
        the orchestrator builds per request); they are additive to any
        tools already baked into the server-side definition.
        """

    def _resolve_definition(self, definition: AgentDefinition) -> AgentDefinition:
        """Apply operator-supplied instruction overrides from `RuntimeConfig`.

        Returns the original `definition` when no override is wired,
        when nothing has been persisted yet, when `definition` is not
        part of the operator-editable set, or when the override is
        empty / whitespace-only (treated as "clear -- fall back to
        the in-code default"). Only `CWYD_AGENT` is editable today;
        `RAI_AGENT` and any future safety surfaces are intentionally
        not exposed through this seam so an operator cannot weaken
        the classifier prompt.

        The accepted override is wrapped by the fixed guardrail via
        the shared `resolve_cwyd_instructions` seam so the authored
        text cannot supersede the non-negotiable safety, out-of-domain,
        and citation rules -- it customizes the persona between the
        guardrail bookends, it does not replace them.
        """
        if self._runtime_overrides_getter is None:
            return definition
        overrides = self._runtime_overrides_getter()
        if overrides is None:
            return definition
        if definition.name != CWYD_AGENT.name:
            return definition
        text = overrides.cwyd_agent_instructions
        if text is None or not text.strip():
            return definition
        return definition.model_copy(
            update={"instructions": resolve_cwyd_instructions(text)}
        )

    async def get_or_create_agent(
        self,
        definition: AgentDefinition,
        db: BaseDatabaseClient,
    ) -> str:
        """Resolve `definition` to a Foundry agent name, creating a
        versioned Prompt Agent on first call and persisting the name
        for next time.

        Foundry's GA control plane addresses a hosted agent by its
        stable *name*: `agents.create_version(name, definition=...)`
        registers (or adds a version to) the named agent, and the
        orchestrator / RAI tool invoke it by that same name. The
        persisted value is therefore the agent name, not an opaque
        per-instance id.

        Algorithm:

        1. Process cache hit -> return immediately. This is the
           steady-state path.
        2. DB lookup (`db.get_agent_id`). On hit, validate the
           persisted name by calling `client.agents.get(...)` -- a
           name with no live Foundry agent (deleted out-of-band,
           environment rebuild) is detected here and falls through to
           step 4.
        3. Per-key lock + double-checked cache. Two concurrent first
           callers race past the cache miss; the second one sees the
           winner's value once the lock releases.
        4. `client.agents.create_version(...)` ->
           `db.upsert_agent_id(...)` -> cache -> return. The
           named-agent registration is idempotent: a concurrent
           worker that wins the create race surfaces as a 409, which
           re-reads the agent and reuses it rather than failing. The
           Foundry write happens before the DB write so a DB failure
           leaves a recoverable state (the next request re-validates
           and re-registers).
        """
        cached = self._agent_cache.get(definition.name)
        if cached is not None:
            return cached

        client = self.get_client()
        deployment = self._settings.openai.gpt_deployment

        persisted = await db.get_agent_id(definition.name)
        if persisted is not None:
            try:
                await client.agents.get(persisted)
            except ResourceNotFoundError:
                # Stale name -- the Foundry agent was deleted out from
                # under us. Fall through to recreate; the upsert in
                # step 4 rewrites the DB row. Intentionally NOT logged
                # at ERROR: environment rebuilds are routine and the
                # recovery is silent.
                persisted = None
            except AzureError:
                # Non-404 azure-core failure (auth, transport, 5xx)
                # is NOT a recovery signal -- surface it so the
                # lifespan / app-level handler maps it to 503.
                logger.exception(
                    "agents client.get_agent failed",
                    extra={
                        "operation": "get_agent",
                        "provider": "agents",
                        "agent_name": definition.name,
                    },
                )
                raise
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

            resolved = self._resolve_definition(definition)
            prompt_definition = PromptAgentDefinition(
                model=deployment,
                instructions=resolved.instructions,
                tools=_definition_tools_to_sdk(resolved.tools),
            )
            try:
                await client.agents.create_version(
                    agent_name=resolved.name,
                    definition=prompt_definition,
                    description=resolved.description,
                )
            except HttpResponseError as exc:
                if exc.status_code != 409:
                    # Non-409 HTTP failure (auth, quota, 5xx) -- do
                    # NOT swallow. The `async with lock:` releases on
                    # the way out so a retry can proceed; partial
                    # state is poisonous so we leave cache + DB alone.
                    logger.exception(
                        "agents client.create_version failed",
                        extra={
                            "operation": "create_version",
                            "provider": "agents",
                            "agent_name": definition.name,
                            "deployment": deployment,
                        },
                    )
                    raise
                # 409: a concurrent worker registered the named agent
                # between our get and create. The named-agent identity
                # is idempotent -- re-read to confirm it resolves, then
                # reuse it. This is recovery, not an error.
                try:
                    await client.agents.get(resolved.name)
                except AzureError:
                    logger.exception(
                        "agents client.get_agent failed",
                        extra={
                            "operation": "get_agent",
                            "provider": "agents",
                            "agent_name": definition.name,
                        },
                    )
                    raise
            except AzureError:
                # Non-HTTP azure-core failure (transport drop, request
                # build) on the create path -- same no-partial-state
                # contract as the non-409 branch above.
                logger.exception(
                    "agents client.create_version failed",
                    extra={
                        "operation": "create_version",
                        "provider": "agents",
                        "agent_name": definition.name,
                        "deployment": deployment,
                    },
                )
                raise

            await db.upsert_agent_id(definition.name, resolved.name)
            self._agent_cache[definition.name] = resolved.name
            return resolved.name
