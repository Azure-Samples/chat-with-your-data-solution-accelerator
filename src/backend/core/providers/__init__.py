"""Plug-and-play providers for v2.

Each subdomain (`credentials/`, `llm/`, `embedders/`, `parsers/`,
`search/`, `chat_history/`, `orchestrators/`) exposes a `Registry[T]`
instance in its sibling `registry.py`; callers resolve a concrete
provider via `registry.get(key)(**kwargs)`.
"""
