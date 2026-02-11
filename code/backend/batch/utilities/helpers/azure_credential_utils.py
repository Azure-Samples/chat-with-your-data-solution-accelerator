import os
from azure.identity import ManagedIdentityCredential, DefaultAzureCredential
from azure.identity.aio import (
    ManagedIdentityCredential as AioManagedIdentityCredential,
    DefaultAzureCredential as AioDefaultAzureCredential,
)


async def get_azure_credential_async(client_id=None):
    """
    Returns an Azure credential asynchronously based on the application environment.

    If the environment is 'dev', it uses AioDefaultAzureCredential.
    Otherwise, it uses AioManagedIdentityCredential.

    Args:
        client_id (str, optional): The client ID for the Managed Identity Credential.

    Returns:
        Credential object: Either AioDefaultAzureCredential or AioManagedIdentityCredential.
    """
    if os.getenv("APP_ENV", "prod").lower() == "dev":
        return (
            AioDefaultAzureCredential()
        )  # CodeQL [SM05139] Okay use of DefaultAzureCredential as it is only used in development
    else:
        return AioManagedIdentityCredential(client_id=client_id)


def get_azure_credential(client_id=None):
    """
    Returns an Azure credential based on the application environment.

    If the environment is 'dev', it uses DefaultAzureCredential.
    Otherwise, it uses ManagedIdentityCredential.

    Args:
        client_id (str, optional): The client ID for the Managed Identity Credential.

    Returns:
        Credential object: Either DefaultAzureCredential or ManagedIdentityCredential.
    """
    if os.getenv("APP_ENV", "prod").lower() == "dev":
        return (
            DefaultAzureCredential()
        )  # CodeQL [SM05139] Okay use of DefaultAzureCredential as it is only used in development
    else:
        return ManagedIdentityCredential(client_id=client_id)
