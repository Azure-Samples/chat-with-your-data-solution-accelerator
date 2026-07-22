"""Content safety guardrail.

Two parallel safety seams live in this module, by design:

1. `ContentSafetyGuard` -- thin async wrapper around Azure AI Content
   Safety (`analyze_text`). Categorical severity scoring (Hate /
   Violence / SelfHarm / Sexual). Constructor takes a built
   `ContentSafetyClient`; production wiring builds the singleton in
   `backend/app.py` lifespan alongside the LLM provider (ADR 0005).

2. `rai_check` -- LLM-based binary classifier delegating to a
   dedicated Foundry agent (`RAI_AGENT` from `shared.agents`). Returns
   `True` when the input is safe to forward to the primary agent,
   `False` when it must be blocked. The two seams run *in parallel*
   (not as fallbacks) -- Content Safety catches categorical harms
   with calibrated severity, the RAI agent catches jailbreaks /
   prompt-injection / policy-bypass attempts that the categorical
   classifier misses (reference-architecture pattern, adapted; v2
   runs the RAI classifier on the shared chat deployment
   (`AZURE_OPENAI_GPT_DEPLOYMENT`) rather than the reference
   architecture's dedicated `AZURE_OPENAI_RAI_DEPLOYMENT_NAME`).

NOT a registry domain. Tools are imported directly:

    from backend.core.tools.content_safety import ContentSafetyGuard, rai_check
"""

import logging

from azure.ai.contentsafety.aio import ContentSafetyClient
from azure.ai.contentsafety.models import AnalyzeTextOptions, TextCategory
from azure.core.exceptions import AzureError
from pydantic import BaseModel, Field

from backend.core.agents.definitions import RAI_AGENT, AgentDefinition
from backend.core.providers.agents.base import BaseAgentsProvider
from backend.core.providers.databases.base import BaseDatabaseClient

logger = logging.getLogger(__name__)


# Severity threshold above which content is flagged. Azure Content
# Safety reports severity 0/2/4/6 (0 = safe, 2 = low, 4 = medium,
# 6 = high). Default trips on `medium` or worse, matching the v1
# default (`enable_content_safety: true` with no per-category tuning).
DEFAULT_SEVERITY_THRESHOLD = 4

# RAI verdict prefix that means "safe to forward". Per
# `RAI_AGENT.instructions` (shared/agents/definitions.py), the
# classifier is instructed to respond with exactly one word -- "TRUE"
# or "FALSE" -- where TRUE means the input is a normal information-
# seeking request and FALSE means it must be blocked. Any other
# response (refusal, empty, or unparseable text) is treated as
# unsafe -- fail-closed is the only safe default for a guard.
_RAI_SAFE_PREFIX = "TRUE"


class ContentSafetyVerdict(BaseModel):
    """Structured result of a `ContentSafetyGuard.screen()` call."""

    flagged: bool
    categories: dict[str, int] = Field(default_factory=dict)
    triggered: list[str] = Field(default_factory=list)


class ContentSafetyGuard:
    def __init__(
        self,
        client: ContentSafetyClient,
        *,
        severity_threshold: int = DEFAULT_SEVERITY_THRESHOLD,
    ) -> None:
        if severity_threshold < 0:
            raise ValueError("severity_threshold must be >= 0")
        self._client = client
        self._threshold = severity_threshold

    async def screen(self, text: str) -> ContentSafetyVerdict:
        """Run the input through Azure Content Safety.

        Empty / whitespace-only input is a no-op (returns `flagged=False`)
        -- the SDK rejects empty payloads and we don't want a guard call
        on an idle prompt to error out.
        """
        if not text or not text.strip():
            return ContentSafetyVerdict(flagged=False)
        result = await self._client.analyze_text(
            AnalyzeTextOptions(text=text, categories=list(TextCategory))
        )
        categories: dict[str, int] = {}
        triggered: list[str] = []
        for analysis in result.categories_analysis or []:
            name = str(analysis.category)
            severity = int(analysis.severity or 0)
            categories[name] = severity
            if severity >= self._threshold:
                triggered.append(name)
        return ContentSafetyVerdict(
            flagged=bool(triggered),
            categories=categories,
            triggered=triggered,
        )


async def rai_check(
    text: str,
    agents: BaseAgentsProvider,
    db: BaseDatabaseClient,
    *,
    agent: AgentDefinition = RAI_AGENT,
) -> bool:
    """Run `text` through a Responsible AI binary classifier.

    Returns `True` when the input is safe to forward, `False` when it
    must be blocked.

    `agent` selects the classifier definition. It defaults to
    `RAI_AGENT`, the user-message screener the chat pipeline uses; the
    admin prompt-save gate passes `PROMPT_REVIEW_AGENT` instead, which
    is calibrated to review operator-authored *system prompts* rather
    than end-user messages (BUG-0084). Both share this TRUE/FALSE
    parsing and fail-closed contract.

    Builds the selected Foundry agent through the shared `build_agent`
    seam -- the same construction path the chat orchestrator uses for
    the primary agent -- then issues a single non-streaming `agent.run`
    and reads the agent's reply text. The named Prompt Agent is
    resolved / created server-side on first use and addressed by its
    stable name thereafter; the client-side `agent_framework.Agent` is
    an async context manager that owns its chat-client transport for
    the duration of the call.

    Verdict parsing: a case-insensitive, whitespace-stripped reply
    that starts with `TRUE` means safe (return `True`). Anything else
    -- `FALSE`, a refusal, empty content, or unparseable prose --
    means unsafe (return `False`). This fail-closed default is the
    only safe behavior for a guard whose output gates whether harmful
    input reaches the primary agent.

    Empty / whitespace-only input is treated as safe and skips the
    Foundry round-trip -- mirrors `ContentSafetyGuard.screen()` and
    avoids spending a round-trip on idle prompts.

    A transport failure of the classifier agent (`AzureError`) is
    logged at the SDK boundary and re-raised rather than degraded to a
    verdict, so an outage surfaces as an error to the caller instead of
    masquerading as a policy block.

    Reference-architecture attribution: the TRUE/FALSE classifier
    prompt shape and the dedicated-agent pattern are adapted from the
    reference architecture. The classifier runs on the shared chat
    deployment instead of the reference architecture's per-RAI env var.
    """
    if not text or not text.strip():
        return True

    built = await agents.build_agent(agent, db)
    async with built:
        try:
            response = await built.run(text)
        except AzureError:
            logger.exception(
                "rai_check agent run failed",
                extra={
                    "operation": "rai_check",
                    "provider": "agent_framework",
                    "agent_name": agent.name,
                },
            )
            raise

    verdict = response.text.strip().upper()
    return verdict.startswith(_RAI_SAFE_PREFIX)
