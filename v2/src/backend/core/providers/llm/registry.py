"""LLM provider registry (single plug-point).

Pillar: Stable Core
Phase: 2

Holds the `Registry[type[BaseLLMProvider]]` instance and the eager
side-effect import of `foundry_iq` (which calls
`@registry.register("foundry_iq")` at import time).

Caller pattern (Hard Rule #13):

    from backend.core.providers.llm import registry as llm_registry

    llm_provider = llm_registry.registry.get("foundry_iq")(
        settings=settings, credential=credential
    )
    reply = await llm_provider.chat(messages, deployment="gpt-4o")
"""

# pyright: reportUnusedImport=false
# `from . import foundry_iq` below is an intentional side-effect
# import that triggers `@registry.register("foundry_iq")`; pyright
# cannot see the side-effect and would flag it as unused (Hard Rule #4).

from ._instance import registry as registry
from . import foundry_iq  # noqa: F401
