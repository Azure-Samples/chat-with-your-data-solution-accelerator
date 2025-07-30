import sys
import os
from unittest.mock import patch, MagicMock
import pytest
import helpers.azure_credential_utils as azure_credential_utils

# Ensure src/backend is on the Python path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

# Synchronous tests


@patch("helpers.azure_credential_utils.os.getenv")
@patch("helpers.azure_credential_utils.DefaultAzureCredential")
@patch("helpers.azure_credential_utils.ManagedIdentityCredential")
def test_get_azure_credential_dev_env(
    mock_managed_identity_credential, mock_default_azure_credential, mock_getenv
):
    """Test get_azure_credential in dev environment."""
    mock_getenv.return_value = "dev"
    mock_default_credential = MagicMock()
    mock_default_azure_credential.return_value = mock_default_credential

    credential = azure_credential_utils.get_azure_credential()

    mock_getenv.assert_called_once_with("APP_ENV", "prod")
    mock_default_azure_credential.assert_called_once()
    mock_managed_identity_credential.assert_not_called()
    assert credential == mock_default_credential


@patch("helpers.azure_credential_utils.os.getenv")
@patch("helpers.azure_credential_utils.DefaultAzureCredential")
@patch("helpers.azure_credential_utils.ManagedIdentityCredential")
def test_get_azure_credential_non_dev_env(
    mock_managed_identity_credential, mock_default_azure_credential, mock_getenv
):
    """Test get_azure_credential in non-dev environment."""
    mock_getenv.return_value = "prod"
    mock_managed_credential = MagicMock()
    mock_managed_identity_credential.return_value = mock_managed_credential
    credential = azure_credential_utils.get_azure_credential(client_id="test-client-id")

    mock_getenv.assert_called_once_with("APP_ENV", "prod")
    mock_managed_identity_credential.assert_called_once_with(client_id="test-client-id")
    mock_default_azure_credential.assert_not_called()
    assert credential == mock_managed_credential


# Asynchronous tests


@pytest.mark.asyncio
@patch("helpers.azure_credential_utils.os.getenv")
@patch("helpers.azure_credential_utils.AioDefaultAzureCredential")
@patch("helpers.azure_credential_utils.AioManagedIdentityCredential")
async def test_get_azure_credential_async_dev_env(
    mock_aio_managed_identity_credential, mock_aio_default_azure_credential, mock_getenv
):
    """Test get_azure_credential_async in dev environment."""
    mock_getenv.return_value = "dev"
    mock_aio_default_credential = MagicMock()
    mock_aio_default_azure_credential.return_value = mock_aio_default_credential

    credential = await azure_credential_utils.get_azure_credential_async()

    mock_getenv.assert_called_once_with("APP_ENV", "prod")
    mock_aio_default_azure_credential.assert_called_once()
    mock_aio_managed_identity_credential.assert_not_called()
    assert credential == mock_aio_default_credential


@pytest.mark.asyncio
@patch("helpers.azure_credential_utils.os.getenv")
@patch("helpers.azure_credential_utils.AioDefaultAzureCredential")
@patch("helpers.azure_credential_utils.AioManagedIdentityCredential")
async def test_get_azure_credential_async_non_dev_env(
    mock_aio_managed_identity_credential, mock_aio_default_azure_credential, mock_getenv
):
    """Test get_azure_credential_async in non-dev environment."""
    mock_getenv.return_value = "prod"
    mock_aio_managed_credential = MagicMock()
    mock_aio_managed_identity_credential.return_value = mock_aio_managed_credential

    credential = await azure_credential_utils.get_azure_credential_async(
        client_id="test-client-id"
    )

    mock_getenv.assert_called_once_with("APP_ENV", "prod")
    mock_aio_managed_identity_credential.assert_called_once_with(
        client_id="test-client-id"
    )
    mock_aio_default_azure_credential.assert_not_called()
    assert credential == mock_aio_managed_credential
