"""Credentials provider ABC."""

from abc import ABC, abstractmethod

from azure.core.credentials_async import AsyncTokenCredential

from backend.core.settings import AppSettings


class BaseCredentialProvider(ABC):
    """Returns an async Azure `TokenCredential` for use with SDK clients.

    Implementations live under `src/backend/core/providers/credentials/` and
    self-register via `@registry.register("<key>")`.
    """

    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings

    @abstractmethod
    async def get_credential(self) -> AsyncTokenCredential:
        """Return an async token credential.

        Callers are expected to use the returned credential as an async
        context manager (`async with await provider.get_credential() as
        cred: ...`) so its underlying HTTP session is closed.
        """
