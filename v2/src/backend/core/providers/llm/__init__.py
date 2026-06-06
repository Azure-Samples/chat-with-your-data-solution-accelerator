"""LLM provider domain (package marker only).

Pillar: Stable Core
Phase: 2

Per Hard Rule #13 / development_plan §2.4: this `__init__.py` is a
package marker only. The `Registry[type[BaseLLMProvider]]` instance
+ eager side-effect imports of concrete providers live in
`registry.py`. Callers:

    from backend.core.providers.llm import registry as llm_registry

    llm_provider = llm_registry.registry.get("foundry_iq")(
        settings=settings, credential=credential
    )
"""
