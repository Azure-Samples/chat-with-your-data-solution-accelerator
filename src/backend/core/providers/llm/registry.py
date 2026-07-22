"""LLM provider registry (single plug-point).

Holds the `Registry[type[BaseLLMProvider]]` instance and the eager
side-effect import of `foundry_iq` (which calls
`@registry.register("foundry_iq")` at import time).

Caller pattern (Hard Rule #13):

    from backend.core.providers.llm import registry as llm_registry

    llm_provider = llm_registry.registry.get("foundry_iq")(
        settings=settings, credential=credential
    )
    reply = await llm_provider.chat(messages, deployment="gpt-5.1")
"""

# pyright: reportUnusedImport=false
# `from . import foundry_iq` below is an intentional side-effect
# import that triggers `@registry.register("foundry_iq")`; pyright
# cannot see the side-effect and would flag it as unused (Hard Rule #4).

from backend.core.discovery import load_entry_points

from ._instance import registry as registry  # noqa: F401
from . import foundry_iq  # noqa: F401

# Third-party plugins self-register via the `cwyd.providers.llm`
# entry-point group per Hard Rule #11 registry-driven carve-out. See
# backend.core.discovery.load_entry_points for the loading contract.
load_entry_points("cwyd.providers.llm")
