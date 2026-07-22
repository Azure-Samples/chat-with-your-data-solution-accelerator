---
title: Customizing azd parameters
description: Override the deployment parameters for Chat with Your Data before running azd up.
ms.date: 2026-07-03
ms.topic: reference
---

[Back to *Chat with your data* README](../README.md)

![Supporting documentation](images/supportingDocuments.png)

## Overview

By default the deployment uses your environment name as a prefix to keep Azure resource names unique. The parameters below show their default values; you only need to set a parameter when you want to change it.

`azd up` prompts you for a few decisions that cannot be defaulted safely: the database type, the AI service region, and the reliability and security flags. Every parameter can also be set ahead of time. To override any parameter, run `azd env set <NAME> <VALUE>` before `azd up`. On the first `azd` command you are prompted for the environment name; choose a 3–16 character alphanumeric name.

## Core configuration

| Name | Type | Default | Purpose |
|------|------|---------|---------|
| `AZURE_ENV_NAME` | string | (prompted) | Environment name prefix for all resources (3–16 alphanumeric characters). |
| `AZURE_LOCATION` | string | (prompted) | Region for the resource group and regional resources. |
| `AZURE_ENV_SOLUTION_NAME` | string | (env name) | Solution name used when composing resource names. |
| `AZURE_ENV_UNIQUE_TEXT` | string | (generated) | Override for the unique suffix applied to resource names. |

## Database

The database type is chosen once and is locked after deployment. It sets both the chat-history store and the retrieval index.

| Name | Type | Default | Purpose |
|------|------|---------|---------|
| `AZURE_ENV_DATABASE_TYPE` | string | `cosmosdb` | `cosmosdb` (Cosmos DB + Azure AI Search) or `postgresql` (PostgreSQL Flexible Server + pgvector). |

See [Chat history](chat_history.md) and [PostgreSQL](postgreSQL.md).

## Azure AI Foundry models

| Name | Type | Default | Purpose |
|------|------|---------|---------|
| `AZURE_ENV_AI_SERVICE_LOCATION` | string | (`AZURE_LOCATION`) | Region for Azure AI Services and Foundry; restricted to regions with capacity for the chat model. |
| `AZURE_ENV_GPT_MODEL_NAME` | string | `gpt-5.1` | Chat model name. |
| `AZURE_ENV_GPT_MODEL_VERSION` | string | `2025-11-13` | Chat model version. |
| `AZURE_ENV_GPT_MODEL_SKU` | string | `GlobalStandard` | Chat model deployment type. |
| `AZURE_ENV_GPT_MODEL_CAPACITY` | integer | `150` | Chat model capacity (TPM, thousands). |
| `AZURE_ENV_EMBEDDING_MODEL_NAME` | string | `text-embedding-3-large` | Embedding model name. |
| `AZURE_ENV_EMBEDDING_MODEL_VERSION` | string | `1` | Embedding model version. |
| `AZURE_ENV_EMBEDDING_MODEL_SKU` | string | `Standard` | Embedding model deployment type. |
| `AZURE_ENV_EMBEDDING_MODEL_CAPACITY` | integer | `100` | Embedding model capacity (TPM, thousands). |

See [Model configuration](model_configuration.md) and [Model quota settings](azure_openai_model_quota_settings.md).

## Ingestion

| Name | Type | Default | Purpose |
|------|------|---------|---------|
| `AZURE_ENV_INGESTION_TRIGGER` | string | `direct_enqueue` | How ingestion starts: `direct_enqueue` (admin uploads enqueue work) or `event_grid` (blob events trigger ingestion). |

See [Document ingestion](document_ingestion.md).

## Reliability and security

These flags align the deployment with the Well-Architected Framework. They are surfaced as prompts by `azd up` and default to `false` for a cost-efficient baseline.

| Name | Type | Default | Purpose |
|------|------|---------|---------|
| `AZURE_ENV_ENABLE_MONITORING` | boolean | `false` | Deploy Log Analytics and Application Insights and wire diagnostic settings. |
| `AZURE_ENV_ENABLE_SCALABILITY` | boolean | `false` | Higher SKUs and autoscale on Container Apps, Azure AI Search, and PostgreSQL. |
| `AZURE_ENV_ENABLE_REDUNDANCY` | boolean | `false` | Zone-redundant and paired-region failover on the data and compute resources. |
| `AZURE_ENV_ENABLE_PRIVATE_NETWORKING` | boolean | `false` | Deploy a virtual network, private endpoints, and Bastion, and disable public network access on data-plane resources. |

## Bring your own resources

To reuse existing resources instead of provisioning new ones, set the matching name. Leave a value empty to have the deployment create the resource.

| Name | Type | Default | Purpose |
|------|------|---------|---------|
| `AZURE_ENV_EXISTING_OPENAI_NAME` | string | (empty) | Reuse an existing Azure AI Services or OpenAI account. |
| `AZURE_ENV_EXISTING_SEARCH_NAME` | string | (empty) | Reuse an existing Azure AI Search service (`cosmosdb` mode). |
| `AZURE_ENV_SEARCH_SERVICE_LOCATION` | string | (empty) | Region for a newly created Azure AI Search service. |
| `AZURE_ENV_EXISTING_COSMOS_NAME` | string | (empty) | Reuse an existing Cosmos DB account (`cosmosdb` mode). |
| `AZURE_ENV_EXISTING_STORAGE_NAME` | string | (empty) | Reuse an existing storage account. |
| `AZURE_ENV_EXISTING_EVENT_GRID_TOPIC_NAME` | string | (empty) | Reuse an existing Event Grid system topic. |

In `postgresql` mode, the person who runs the deployment is set as the PostgreSQL Entra administrator by default. Override with `AZURE_ENV_POSTGRES_ADMIN_PRINCIPAL_ID`, `AZURE_ENV_POSTGRES_ADMIN_PRINCIPAL_NAME`, and `AZURE_ENV_POSTGRES_ADMIN_PRINCIPAL_TYPE`.

## How to set a parameter

Set a parameter before `azd up`:

```bash
azd env set <NAME> <VALUE>
```

### Examples

Set the deployment region:

```bash
azd env set AZURE_LOCATION eastus2
```

Deploy in PostgreSQL mode:

```bash
azd env set AZURE_ENV_DATABASE_TYPE postgresql
```

Turn on monitoring and private networking:

```bash
azd env set AZURE_ENV_ENABLE_MONITORING true
azd env set AZURE_ENV_ENABLE_PRIVATE_NETWORKING true
```

## Notes

* **Region availability.** Not every service or model is available in every region. Confirm availability for your chosen region before deploying; see [Check quota by region](QuotaCheck.md).
* **Locked after deploy.** The database type cannot change after deployment. To switch, deploy a new environment.
* **Orchestrator selection.** The chat orchestrator has no dedicated azd parameter. `azd up` sets it automatically from the `databaseType` choice: `postgresql` selects `langgraph`, and `cosmosdb` selects `agent_framework`. To run a different orchestrator than that default, switch it at runtime from the admin Configuration page with no redeploy; both orchestrators are served on either store. See [Admin and configuration](admin.md#configuration) and [Architecture overview](architecture.md#orchestrators).
