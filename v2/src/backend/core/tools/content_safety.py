"""Content safety guardrail.

Pillar: Stable Core
Phase: 3

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
   classifier misses (MACAE pattern -- `common/utils/utils_af.py`
   `create_RAI_agent`, adapted; v2 collapses MACAE's per-RAI env var
   `AZURE_OPENAI_RAI_DEPLOYMENT_NAME` into the
   `AgentDefinition.deployment_attr` indirection).

NOT a registry domain. Tools are imported directly:

    from backend.core.tools.content_safety import ContentSafetyGuard, rai_check
"""

from azure.ai.agents.models import ListSortOrder, MessageRole
from azure.ai.contentsafety.aio import ContentSafetyClient
from azure.ai.contentsafety.models import AnalyzeTextOptions, TextCategory
from pydantic import BaseModel, Field

from backend.core.agents.definitions import RAI_AGENT
from backend.core.providers.agents.base import BaseAgentsProvider
from backend.core.providers.databases.base import BaseDatabaseClient


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
#
# Note: cleanup_audit.md CU-011a prose says "verdict starts with
# `FALSE`" -- that's a typo. The agent's own instructions are the
# source of truth and `RAI_AGENT.instructions` says TRUE = safe.
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
) -> bool:
    """Run `text` through the Responsible AI binary classifier.

    Returns `True` when the input is safe to forward to the primary
    agent, `False` when it must be blocked.

    Algorithm (single-turn, fresh thread per call):

    1. Resolve the RAI agent id via the lazy DB-backed resolver landed
       in CU-010c (`agents.get_or_create_agent(RAI_AGENT, db)`). This
       creates the agent in Foundry on first call, persists the id in
       the chat-history database, and caches the result for every
       subsequent process-local call.
    2. Create a fresh thread, post `text` as a user message, process a
       run against the resolved agent.
    3. Read the first assistant message produced by *this* run (filtered
       by `run_id` to ignore prior turns -- defensive, since wiring uses
       a fresh thread per call today).
    4. Parse the response: case-insensitive whitespace-stripped prefix
       `TRUE` -> safe (return `True`). Anything else (`FALSE`, refusal,
       empty content, unparseable, run failure) -> unsafe (return
       `False`). This fail-closed default is the only safe behavior for
       a guard whose output gates whether harmful input reaches the
       primary agent.

    Empty / whitespace-only input is treated as safe and skips the
    Foundry round-trip -- mirrors `ContentSafetyGuard.screen()` and
    avoids spending a round-trip on idle prompts.

    MACAE attribution: the TRUE/FALSE classifier prompt shape and the
    "dedicated agent on its own deployment" pattern are adapted from
    `common/utils/utils_af.py::create_RAI_agent`. v2 deviations:
    (a) lazy DB-backed resolution instead of MACAE's env-var
    `AZURE_OPENAI_RAI_DEPLOYMENT_NAME`; (b) `AgentDefinition` carries
    the system prompt + deployment indirection so the resolver is
    agent-agnostic.
    """
    if not text or not text.strip():
        return True

    agent_id = await agents.get_or_create_agent(RAI_AGENT, db)
    client = agents.get_client()

    thread = await client.threads.create()
    await client.messages.create(
        thread_id=thread.id,
        role=MessageRole.USER,
        content=text,
    )
    run = await client.runs.create_and_process(
        thread_id=thread.id,
        agent_id=agent_id,
    )
    if getattr(run, "status", None) == "failed":
        return False

    async for thread_msg in client.messages.list(
        thread_id=thread.id,
        run_id=run.id,
        order=ListSortOrder.ASCENDING,
    ):
        if thread_msg.role != MessageRole.AGENT:
            continue
        verdict = _extract_text(thread_msg).strip().upper()
        if not verdict:
            continue
        return verdict.startswith(_RAI_SAFE_PREFIX)

    # No assistant message produced -- treat as unsafe (fail-closed).
    return False


def _extract_text(thread_msg: object) -> str:
    """Pull the text out of a Foundry `ThreadMessage`.

    Agent message content is a list of typed blocks (text, image,
    file). We concatenate all text blocks in order; non-text blocks
    are ignored. Mirrors `AgentFrameworkOrchestrator._extract_text`
    (orchestrators/agent_framework.py); duplicated rather than
    cross-imported because tools and orchestrators live in independent
    layers and a one-line helper isn't worth a shared dependency.
    """
    parts: list[str] = []
    for block in getattr(thread_msg, "content", []) or []:
        text_block = getattr(block, "text", None)
        value = getattr(text_block, "value", None) if text_block is not None else None
        if value:
            parts.append(value)
    return "".join(parts)
