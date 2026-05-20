"""Plug-and-play providers for v2.

Pillar: Stable Core
Phase: 2

Each subdomain (`credentials/`, `llm/`, `embedders/`, `parsers/`,
`search/`, `chat_history/`, `orchestrators/`) exposes a `Registry[T]`
plus a `create(key, **kwargs)` helper. See §3.5 of
`v2/docs/development_plan.md` for the binding recipe.
"""
