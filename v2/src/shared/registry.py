"""
Generic in-process Registry primitive.

Pillar: Stable Core
Phase: 1

Used by every shared/* domain (embedders, orchestrators, search, chat_history,
llm, parsers, credentials) to register provider classes by string key. Providers
self-register at import time via the @registry.register("key") decorator. Domain
__init__.py modules eager-import every provider module to trigger registration,
then expose a thin .create(key, **kwargs) helper. This eliminates the if/else
factory dispatch and lazy in-function imports that polluted v1.
"""
from __future__ import annotations

from typing import Callable, Generic, TypeVar

T = TypeVar("T")


class Registry(Generic[T]):
    """Case-insensitive string-keyed registry of types/factories.

    Example
    -------
    >>> embedders: Registry[type[BaseEmbedder]] = Registry("embedders")
    >>> @embedders.register("AzureSearch")
    ... class FoundryKbEmbedder(BaseEmbedder): ...
    >>> cls = embedders.get("azuresearch")  # case-insensitive
    """

    def __init__(self, domain: str) -> None:
        if not domain:
            raise ValueError("Registry domain must be a non-empty string")
        self._domain = domain
        self._items: dict[str, T] = {}

    @property
    def domain(self) -> str:
        return self._domain

    def register(self, key: str) -> Callable[[T], T]:
        """Decorator that records `value` under the normalized `key`.

        Re-registering the same key with a different value raises ValueError.
        Re-registering the identical value (idempotent reload) is a no-op.
        """
        if not key:
            raise ValueError(f"{self._domain}: registration key must be non-empty")
        normalized = key.lower()

        def _decorate(value: T) -> T:
            existing = self._items.get(normalized)
            if existing is not None and existing is not value:
                raise ValueError(
                    f"{self._domain}: key '{key}' is already registered to "
                    f"{existing!r}; refusing to overwrite with {value!r}"
                )
            self._items[normalized] = value
            return value

        return _decorate

    def get(self, key: str) -> T:
        """Look up a registered value. Raises KeyError listing available keys."""
        normalized = (key or "").lower()
        try:
            return self._items[normalized]
        except KeyError as exc:
            available = ", ".join(sorted(self._items)) or "<none>"
            raise KeyError(
                f"{self._domain}: no provider registered for '{key}'. "
                f"Available: {available}"
            ) from exc

    def keys(self) -> list[str]:
        return sorted(self._items)

    def __contains__(self, key: object) -> bool:
        return isinstance(key, str) and key.lower() in self._items

    def __len__(self) -> int:
        return len(self._items)
