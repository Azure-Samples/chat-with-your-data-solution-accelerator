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

`azd up` prompts you only for values that are unset and have no default, such as the environment name and the deployment region. Every other parameter listed below ships with a safe default (shown in the tables) and is used unless you override it. To override any parameter, run `azd env set <NAME> <VALUE>` before `azd up`. On the first `azd` command you are prompted for the environment name; choose a 3–16 character alphanumeric name.

## Core configuration

| Name | Type | Default | Purpose |
|------|------|---------|---------|
| `AZURE_ENV_NAME` | string | (prompted) | Environment name prefix for all resources (3–16 alphanumeric characters). |
| `AZURE_LOCATION` | string | (prompted) | Region for the resource group and regional resources. |

## Database

The database type is chosen once and is locked after deployment. It sets both the chat-history store and the retrieval index.

| Name | Type | Default | Purpose |
|------|------|---------|---------|
| `DATABASE_TYPE` | string | `postgresql` | `postgresql` (PostgreSQL Flexible Server + pgvector) or `cosmosdb` (Cosmos DB + Azure AI Search). |

See [Chat history](chat_history.md) and [PostgreSQL](postgreSQL.md).

## Azure AI Foundry models

| Name | Type | Default | Purpose |
|------|------|---------|---------|
| `AZURE_AI_SERVICE_LOCATION` | string | (`AZURE_LOCATION`) | Region for Azure AI Services and Foundry; restricted to regions with capacity for the chat model. |
| `AZURE_GPT_MODEL_NAME` | string | `gpt-5.4-mini` | Chat model name. |
| `AZURE_GPT_MODEL_VERSION` | string | `2026-03-17` | Chat model version. |
| `AZURE_GPT_MODEL_DEPLOYMENT_TYPE` | string | `GlobalStandard` | Chat model deployment type. |
| `AZURE_GPT_MODEL_CAPACITY` | integer | `50` | Chat model capacity (TPM, thousands). |
| `AZURE_REASONING_MODEL_NAME` | string | `gpt-5-mini` | Reasoning model name. |
| `AZURE_REASONING_MODEL_VERSION` | string | `2025-08-07` | Reasoning model version. |
| `AZURE_REASONING_MODEL_DEPLOYMENT_TYPE` | string | `GlobalStandard` | Reasoning model deployment type. |
| `AZURE_REASONING_MODEL_CAPACITY` | integer | `50` | Reasoning model capacity (TPM, thousands). |
| `AZURE_EMBEDDING_MODEL_NAME` | string | `text-embedding-3-small` | Embedding model name. |
| `AZURE_EMBEDDING_MODEL_VERSION` | string | `1` | Embedding model version. |
| `AZURE_EMBEDDING_MODEL_DEPLOYMENT_TYPE` | string | `Standard` | Embedding model deployment type. |
| `AZURE_EMBEDDING_MODEL_CAPACITY` | integer | `100` | Embedding model capacity (TPM, thousands). |
| `AZURE_OPENAI_API_VERSION` | string | `2025-01-01-preview` | API version for chat and embedding calls. |
| `AZURE_AI_AGENT_API_VERSION` | string | `2025-05-01` | API version for the Foundry agent runtime. |

See [Model configuration](model_configuration.md) and [Model quota settings](azure_openai_model_quota_settings.md).

## Ingestion

| Name | Type | Default | Purpose |
|------|------|---------|---------|
| `INGESTION_TRIGGER` | string | `direct_enqueue` | How ingestion starts: `direct_enqueue` (admin uploads enqueue work) or `event_grid` (blob events trigger ingestion). |

See [Document ingestion](document_ingestion.md).

## Reliability and security

These flags align the deployment with the Well-Architected Framework and apply to the WAF deployment profile (`main.waf.parameters.json`).

| Name | Type | Default | Purpose |
|------|------|---------|---------|
| `ENABLE_TELEMETRY` | boolean | `true` | Send anonymized module usage telemetry. |
| `ENABLE_MONITORING` | boolean | `false` | Deploy Log Analytics and Application Insights and wire diagnostic settings. |
| `ENABLE_SCALABILITY` | boolean | `true` | Higher SKUs and autoscale on Container Apps, Azure AI Search, and PostgreSQL. |
| `ENABLE_REDUNDANCY` | boolean | `false` | Zone-redundant and paired-region failover on the data and compute resources. |
| `ENABLE_PRIVATE_NETWORKING` | boolean | `true` | Deploy a virtual network, private endpoints, and Bastion, and disable public network access on data-plane resources. |
| `AZURE_ENV_VM_ADMIN_USERNAME` | string | (empty) | Jumpbox VM admin username (used when private networking is enabled). |
| `AZURE_ENV_VM_ADMIN_PASSWORD` | string | (empty) | Jumpbox VM admin password (used when private networking is enabled). |
| `AZURE_ENV_JUMPBOX_SIZE` | string | `Standard_D2s_v5` | Jumpbox VM size (used when private networking is enabled). |

## Bring your own resources

To reuse existing resources instead of provisioning new ones, set the matching resource ID. Leave a value empty to have the deployment create the resource.

| Name | Type | Default | Purpose |
|------|------|---------|---------|
| `AZURE_ENV_LOG_ANALYTICS_WORKSPACE_ID` | string | (empty) | Resource ID of an existing Log Analytics workspace. |
| `AZURE_EXISTING_AIPROJECT_RESOURCE_ID` | string | (empty) | Resource ID of an existing AI Foundry project. |

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
azd env set DATABASE_TYPE postgresql
```

Turn on monitoring and private networking:

```bash
azd env set ENABLE_MONITORING true
azd env set ENABLE_PRIVATE_NETWORKING true
```

## Notes

* **Region availability.** Not every service or model is available in every region. Confirm availability for your chosen region before deploying; see [Check quota by region](QuotaCheck.md).
* **Locked after deploy.** The database type cannot change after deployment. To switch, deploy a new environment.
* **Orchestrator selection.** The chat orchestrator has no dedicated azd parameter. `azd up` sets it automatically from the `databaseType` choice: `postgresql` selects `langgraph`, and `cosmosdb` selects `agent_framework`. To run a different orchestrator than that default, switch it at runtime from the admin Configuration page with no redeploy; both orchestrators are served on either store. See [Admin and configuration](admin.md#configuration) and [Architecture overview](architecture.md#orchestrators).
