"""Tests for the credentials provider domain (Phase 2 task #11).

Pillar: Stable Core
Phase: 2
"""

import importlib
from unittest.mock import patch

import pytest
from azure.identity.aio import AzureCliCredential, DefaultAzureCredential

from backend.core.providers.credentials import registry as credentials_registry
from backend.core.providers.credentials.base import BaseCredentialProvider
from backend.core.providers.credentials.cli import CliCredentialProvider
from backend.core.providers.credentials.managed_identity import ManagedIdentityCredentialProvider
from backend.core.settings import AppSettings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


COSMOS_ENV: dict[str, str] = {
    "AZURE_SOLUTION_SUFFIX": "cwyd001",
    "AZURE_RESOURCE_GROUP": "rg-cwyd-001",
    "AZURE_LOCATION": "eastus2",
    "AZURE_TENANT_ID": "00000000-0000-0000-0000-000000000001",
    "AZURE_DB_TYPE": "cosmosdb",
    "AZURE_INDEX_STORE": "AzureSearch",
    "AZURE_COSMOS_ENDPOINT": "https://cosmos-cwyd001.documents.azure.com:443/",
}


@pytest.fixture
def settings_with_uami(monkeypatch: pytest.MonkeyPatch) -> AppSettings:
    for key, value in COSMOS_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv(
        "AZURE_UAMI_CLIENT_ID", "00000000-0000-0000-0000-000000000002"
    )
    return AppSettings()


@pytest.fixture
def settings_without_uami(monkeypatch: pytest.MonkeyPatch) -> AppSettings:
    for key, value in COSMOS_ENV.items():
        monkeypatch.setenv(key, value)
    return AppSettings()  # uami_client_id == ""


# ---------------------------------------------------------------------------
# Registry wiring
# ---------------------------------------------------------------------------


def test_registry_contains_both_providers() -> None:
    assert "managed_identity" in credentials_registry.registry
    assert "cli" in credentials_registry.registry


def test_registry_is_case_insensitive() -> None:
    assert credentials_registry.registry.get("MANAGED_IDENTITY") is ManagedIdentityCredentialProvider
    assert credentials_registry.registry.get("Cli") is CliCredentialProvider


def test_create_returns_provider_instances(settings_with_uami: AppSettings) -> None:
    mi = credentials_registry.registry.get("managed_identity")(settings=settings_with_uami)
    cli = credentials_registry.registry.get("cli")(settings=settings_with_uami)
    assert isinstance(mi, ManagedIdentityCredentialProvider)
    assert isinstance(cli, CliCredentialProvider)
    assert isinstance(mi, BaseCredentialProvider)


def test_unknown_key_raises(settings_with_uami: AppSettings) -> None:
    with pytest.raises(KeyError):
        credentials_registry.registry.get("workload_identity")(settings=settings_with_uami)


# ---------------------------------------------------------------------------
# select_default heuristic
# ---------------------------------------------------------------------------


def test_select_default_prefers_managed_identity_when_uami_set() -> None:
    assert credentials_registry.select_default("00000000-0000-0000-0000-000000000002") == "managed_identity"


def test_select_default_falls_back_to_cli_when_uami_missing() -> None:
    assert credentials_registry.select_default("") == "cli"
    assert credentials_registry.select_default(None) == "cli"


# ---------------------------------------------------------------------------
# get_credential() returns the right SDK type
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_managed_identity_returns_default_azure_credential(
    settings_with_uami: AppSettings,
) -> None:
    provider = credentials_registry.registry.get("managed_identity")(settings=settings_with_uami)
    cred = await provider.get_credential()
    try:
        assert isinstance(cred, DefaultAzureCredential)
    finally:
        await cred.close()


@pytest.mark.asyncio
async def test_cli_returns_azure_cli_credential(
    settings_without_uami: AppSettings,
) -> None:
    provider = credentials_registry.registry.get("cli")(settings=settings_without_uami)
    cred = await provider.get_credential()
    try:
        assert isinstance(cred, AzureCliCredential)
    finally:
        await cred.close()


# ---------------------------------------------------------------------------
# Constructor contract
# ---------------------------------------------------------------------------


def test_provider_stores_settings_reference(settings_with_uami: AppSettings) -> None:
    provider = credentials_registry.registry.get("managed_identity")(settings=settings_with_uami)
    # _settings is a private attribute but verifying the constructor
    # contract guards against future regressions where a provider
    # forgets to call super().__init__().
    assert provider._settings is settings_with_uami  # noqa: SLF001


# ---------------------------------------------------------------------------
# Entry-point discovery wiring (Hard Rule #11 registry-driven carve-out).
# ---------------------------------------------------------------------------


def test_first_party_keys_registered_at_import() -> None:
    """The eager `from . import cli, managed_identity` side-effect import
    must populate both first-party keys against the credentials registry
    by the time the module finishes loading.
    """
    registered = set(credentials_registry.registry.keys())
    assert {"cli", "managed_identity"}.issubset(registered), (
        f"first-party credentials keys missing from registry: "
        f"registered={registered!r}"
    )


def test_load_entry_points_fires_for_canonical_group() -> None:
    """Third-party discovery hook fires at registry import time with the
    canonical `cwyd.providers.credentials` group string. Patches the
    discovery module then reloads the registry so the freshly bound
    name resolves to the mock; restores the real binding in `finally`
    to keep test isolation.
    """
    with patch("backend.core.discovery.load_entry_points") as mock_load:
        importlib.reload(credentials_registry)
        try:
            mock_load.assert_called_once_with("cwyd.providers.credentials")
        finally:
            importlib.reload(credentials_registry)
