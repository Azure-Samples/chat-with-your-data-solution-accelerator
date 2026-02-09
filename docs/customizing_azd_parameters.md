# Customizing Azure Deployment Parameters

By default this template will use the environment name as the prefix to prevent naming collisions within Azure. The parameters below show the default values. You only need to run the statements below if you need to change the values.

> To override any of the parameters, run `azd env set <PARAMETER_NAME> <VALUE>` before running `azd up`. On the first azd command, it will prompt you for the environment name. Be sure to choose 3-16 characters alphanumeric unique name.

## Core Configuration Parameters

| **Name** | **Type** | **Default Value** | **Purpose** |
|----------|----------|-------------------|-------------|
| `AZURE_ENV_NAME` | string | (prompted) | Sets the environment name prefix for all Azure resources (3-16 alphanumeric characters) |
| `AZURE_LOCATION` | string | (prompted) | Sets the primary location/region for all Azure resources |
| `APP_ENV` | string | `Prod` | Application environment (Prod, Dev, etc.) |

## Application Hosting Parameters

| **Name** | **Type** | **Default Value** | **Purpose** |
|----------|----------|-------------------|-------------|
| `AZURE_APP_SERVICE_HOSTING_MODEL` | string | `container` | Hosting model for web apps (container or code) |
| `HOSTING_PLAN_SKU` | string | `B3` | App Service plan pricing tier (B2, B3, S1, S2) |

## Database Configuration

| **Name** | **Type** | **Default Value** | **Purpose** |
|----------|----------|-------------------|-------------|
| `DATABASE_TYPE` | string | `PostgreSQL` | Type of database to deploy (PostgreSQL or CosmosDB) |

## Azure AI Configurations

| **Name** | **Type** | **Default Value** | **Purpose** |
|----------|----------|-------------------|-------------|
| `AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION` | boolean | `false` | Enable integrated vectorization (must be false for PostgreSQL) |
| `AZURE_SEARCH_USE_SEMANTIC_SEARCH` | boolean | `false` | Enable semantic search capabilities |
| `AZURE_OPENAI_SKU_NAME` | string | `S0` | Azure OpenAI resource SKU |
| `AZURE_OPENAI_MODEL` | string | `gpt-4.1` | Model deployment name |
| `AZURE_OPENAI_MODEL_NAME` | string | `gpt-4.1` | Actual model name |
| `AZURE_OPENAI_MODEL_VERSION` | string | `2025-04-14` | Model version |
| `AZURE_OPENAI_MODEL_CAPACITY` | integer | `150` | Model capacity (TPM in thousands) |
| `AZURE_OPENAI_API_VERSION` | string | `2024-02-01` | Azure OpenAI API version |
| `AZURE_OPENAI_STREAM` | boolean | `true` | Enable streaming responses |
| `AZURE_OPENAI_EMBEDDING_MODEL` | string | `text-embedding-ada-002` | Embedding model deployment name |
| `AZURE_OPENAI_EMBEDDING_MODEL_NAME` | string | `text-embedding-ada-002` | Actual embedding model name |
| `AZURE_OPENAI_EMBEDDING_MODEL_VERSION` | string | `2` | Embedding model version |
| `AZURE_OPENAI_EMBEDDING_MODEL_CAPACITY` | integer | `100` | Embedding model capacity (TPM in thousands) |
| `AZURE_SEARCH_DIMENSIONS` | integer | `1536` | Azure Search vector dimensions(Update dimensions for CosmosDB) |
| `USE_ADVANCED_IMAGE_PROCESSING` | boolean | `false` | Enable vision LLM and Computer Vision for images (must be false for PostgreSQL) |
| `ADVANCED_IMAGE_PROCESSING_MAX_IMAGES` | integer | `1` | Maximum images per vision model request |
| `AZURE_OPENAI_VISION_MODEL` | string | `gpt-4.1` | Vision model deployment name |
| `AZURE_OPENAI_VISION_MODEL_NAME` | string | `gpt-4.1` | Actual vision model name |
| `AZURE_OPENAI_VISION_MODEL_VERSION` | string | `2025-04-14` | Vision model version |
| `AZURE_OPENAI_VISION_MODEL_CAPACITY` | integer | `10` | Vision model capacity (TPM in thousands) |
| `AZURE_COMPUTER_VISION_LOCATION` | string | (empty) | Location for Computer Vision resource |
| `COMPUTER_VISION_SKU_NAME` | string | `S1` | Computer Vision SKU (F0 or S1) |
| `AZURE_COMPUTER_VISION_VECTORIZE_IMAGE_API_VERSION` | string | `2024-02-01` | API version for image vectorization |
| `AZURE_COMPUTER_VISION_VECTORIZE_IMAGE_MODEL_VERSION` | string | `2023-04-15` | Model version for image vectorization |
| `AZURE_SPEECH_RECOGNIZER_LANGUAGES` | string | `en-US,fr-FR,de-DE,it-IT` | Comma-separated list of speech recognition languages |

## Virtual Machine Configuration (Production Only)

| **Name** | **Type** | **Default Value** | **Purpose** |
|----------|----------|-------------------|-------------|
| `AZURE_ENV_JUMPBOX_SIZE` | string | (empty) | Size of the jump box VM |
| `AZURE_ENV_VM_ADMIN_USERNAME` | string | (auto-generated) | Administrator username for VMs |
| `AZURE_ENV_VM_ADMIN_PASSWORD` | string | (auto-generated) | Administrator password for VMs |


## How to Set a Parameter

To customize any of the above values, run the following command **before** `azd up`:

```bash
azd env set <PARAMETER_NAME> <VALUE>
```

### Examples

**Set a custom Azure region:**
```bash
azd env set AZURE_LOCATION eastus2
```

**Configure Azure OpenAI model capacity:**
```bash
azd env set AZURE_OPENAI_MODEL_CAPACITY 200
azd env set AZURE_OPENAI_EMBEDDING_MODEL_CAPACITY 150
```

## Important Notes

1. **PostgreSQL Limitations**: When using `DATABASE_TYPE=PostgreSQL`, you must set:
   - `AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION=false`
   - `USE_ADVANCED_IMAGE_PROCESSING=false`
   - `ORCHESTRATION_STRATEGY=semantic_kernel` (recommended)
   - `AZURE_SEARCH_DIMENSIONS=1536` (recommended)

2. **Region Compatibility**: Not all services are available in all regions. Verify service availability in your chosen region before deployment.
