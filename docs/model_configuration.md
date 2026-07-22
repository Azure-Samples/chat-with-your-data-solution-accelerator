---
title: Model configuration
description: Configure the Azure AI Foundry chat and embedding models used by Chat with Your Data.
ms.date: 2026-07-03
ms.topic: reference
---

[Back to *Chat with your data* README](../README.md)

![Supporting documentation](images/supportingDocuments.png)

## Overview

Chat with Your Data uses two Azure AI Foundry model deployments (a chat model and an embedding model) as its single inference surface. The backend calls Foundry with the workload's managed identity, so there are no model API keys to store. This guide lists the settings that control which models are deployed and how they are sized.

## Available models

For the models and versions available in each region, see the [Azure AI Foundry models documentation](https://learn.microsoft.com/azure/ai-foundry/concepts/models-featured).

## Default deployments

| Purpose | Model | Version | Deployment type | Capacity (TPM, thousands) |
|---------|-------|---------|-----------------|---------------------------|
| Chat | `gpt-5.1` | `2025-11-13` | GlobalStandard | 150 |
| Embeddings | `text-embedding-3-large` | `1` | Standard | 100 |

## Chat model parameters

| Parameter | Example | Purpose |
|-----------|---------|---------|
| `AZURE_ENV_GPT_MODEL_NAME` | `gpt-5.1` | Chat model name. |
| `AZURE_ENV_GPT_MODEL_VERSION` | `2025-11-13` | Chat model version. |
| `AZURE_ENV_GPT_MODEL_SKU` | `GlobalStandard` | Chat model deployment type. |
| `AZURE_ENV_GPT_MODEL_CAPACITY` | `150` | Tokens-per-minute limit (thousands). |

## Embedding model parameters

| Parameter | Example | Purpose |
|-----------|---------|---------|
| `AZURE_ENV_EMBEDDING_MODEL_NAME` | `text-embedding-3-large` | Embedding model name. |
| `AZURE_ENV_EMBEDDING_MODEL_VERSION` | `1` | Embedding model version. |
| `AZURE_ENV_EMBEDDING_MODEL_SKU` | `Standard` | Embedding model deployment type. |
| `AZURE_ENV_EMBEDDING_MODEL_CAPACITY` | `100` | Tokens-per-minute limit (thousands). |

The embedding model sets the vector dimensions written to the retrieval index. `text-embedding-3-large` produces 3072-dimensional vectors. In PostgreSQL mode, the vector column width is set from this dimension when the index is first created; see [PostgreSQL](postgreSQL.md).

## API version parameters

| Parameter | Example | Purpose |
|-----------|---------|---------|
| `AZURE_ENV_OPENAI_API_VERSION` | `2025-01-01-preview` | API version for chat and embedding calls. |
| `AZURE_ENV_AI_AGENT_API_VERSION` | `2025-05-01` | API version for the Foundry agent runtime. |

## Set and read parameters

Set a parameter before `azd up`:

```bash
azd env set <NAME> <VALUE>
```

Read the current values for your environment:

```bash
azd env get-values
```

For the full parameter list, including quota and region settings, see [Customizing azd parameters](customizing_azd_parameters.md) and [Model quota settings](azure_openai_model_quota_settings.md).

## Related documentation

* [Customizing azd parameters](customizing_azd_parameters.md)
* [Model quota settings](azure_openai_model_quota_settings.md)
* [PostgreSQL](postgreSQL.md)
