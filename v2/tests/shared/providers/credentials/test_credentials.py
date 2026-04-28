"""Tests for the credentials provider domain (Phase 2 task #11).

Pillar: Stable Core
Phase: 2
"""
from __future__ import annotations

import pytest
from azure.identity.aio import AzureCliCredential, DefaultAzureCredential

from shared.providers import credentials
from shared.providers.credentials.base import BaseCredentialProvider
from shared.providers.credentials.cli import CliCredentialProvider
from shared.providers.credentials.managed_identity import ManagedIdentityCredentialProvider
from shared.settings import AppSettings


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
    assert "managed_identity" in credentials.registry
    assert "cli" in credentials.registry


def test_registry_is_case_insensitive() -> None:
    assert credentials.registry.get("MANAGED_IDENTITY") is ManagedIdentityCredentialProvider
    assert credentials.registry.get("Cli") is CliCredentialProvider


def test_create_returns_provider_instances(settings_with_uami: AppSettings) -> None:
    mi = credentials.create("managed_identity", settings=settings_with_uami)
    cli = credentials.create("cli", settings=settings_with_uami)
    assert isinstance(mi, ManagedIdentityCredentialProvider)
    assert isinstance(cli, CliCredentialProvider)
    assert isinstance(mi, BaseCredentialProvider)


def test_unknown_key_raises(settings_with_uami: AppSettings) -> None:
    with pytest.raises(KeyError):
        credentials.create("workload_identity", settings=settings_with_uami)


# ---------------------------------------------------------------------------
# select_default heuristic
# ---------------------------------------------------------------------------


def test_select_default_prefers_managed_identity_when_uami_set() -> None:
    assert credentials.select_default("00000000-0000-0000-0000-000000000002") == "managed_identity"


def test_select_default_falls_back_to_cli_when_uami_missing() -> None:
    assert credentials.select_default("") == "cli"
    assert credentials.select_default(None) == "cli"


# ---------------------------------------------------------------------------
# get_credential() returns the right SDK type
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_managed_identity_returns_default_azure_credential(
    settings_with_uami: AppSettings,
) -> None:
    provider = credentials.create("managed_identity", settings=settings_with_uami)
    cred = await provider.get_credential()
    try:
        assert isinstance(cred, DefaultAzureCredential)
    finally:
        await cred.close()


@pytest.mark.asyncio
async def test_cli_returns_azure_cli_credential(
    settings_without_uami: AppSettings,
) -> None:
    provider = credentials.create("cli", settings=settings_without_uami)
    cred = await provider.get_credential()
    try:
        assert isinstance(cred, AzureCliCredential)
    finally:
        await cred.close()


# ---------------------------------------------------------------------------
# Constructor contract
# ---------------------------------------------------------------------------


def test_provider_stores_settings_reference(settings_with_uami: AppSettings) -> None:
    provider = credentials.create("managed_identity", settings=settings_with_uami)
    # _settings is a private attribute but verifying the constructor
    # contract guards against future regressions where a provider
    # forgets to call super().__init__().
    assert provider._settings is settings_with_uami  # noqa: SLF001
