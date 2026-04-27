"""Credentials provider ABC.

Pillar: Stable Core
Phase: 2
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from azure.core.credentials_async import AsyncTokenCredential

    from shared.settings import AppSettings


class BaseCredentialProvider(ABC):
    """Returns an async Azure `TokenCredential` for use with SDK clients.

    Implementations live under `v2/src/providers/credentials/` and
    self-register via `@registry.register("<key>")`.
    """

    def __init__(self, settings: "AppSettings") -> None:
        self._settings = settings

    @abstractmethod
    async def get_credential(self) -> "AsyncTokenCredential":
        """Return an async token credential.

        Callers are expected to use the returned credential as an async
        context manager (`async with await provider.get_credential() as
        cred: ...`) so its underlying HTTP session is closed.
        """
