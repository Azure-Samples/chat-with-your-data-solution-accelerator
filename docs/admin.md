---
title: Admin and configuration
description: Manage documents and application settings from the admin pages built into the Chat with Your Data web app.
ms.date: 2026-07-03
ms.topic: how-to
---

[Back to *Chat with your data* README](../README.md)

![Supporting documentation](images/supportingDocuments.png)

## Overview

Administration is part of the web app. There is no separate admin site to deploy or sign in to. The admin area appears in the same application under `/admin`, where you can ingest documents, remove them, and adjust application settings.

> [!NOTE]
> Replace the images below with screenshots of your deployment.

## Access control

End users sign in interactively through the Container Apps built-in authentication (Easy Auth). The admin area is reached through the same app at `/admin`, and you control who can open it at the identity provider or ingress layer rather than with an in-app role check. See [App authentication setup](authentication_setup.md) for how to restrict admin access.

## Admin pages

The admin area has three pages.

| Page | Purpose |
|------|---------|
| Ingest | Upload documents or submit a URL to add content to the index. |
| Delete | Remove documents from the index and their source blobs. |
| Configuration | Review and adjust application settings, including the chat orchestrator. |

![Admin ingest page](images/admin-ingest.png)

## Ingest documents

Use the Ingest page to upload files or submit a URL. Uploaded content is stored, queued, and processed by the ingestion worker, which parses, chunks, embeds, and indexes it. For the pipeline details, see [Document ingestion](document_ingestion.md). For the file types you can upload, see [Supported file types](supported_file_types.md).

## Delete documents

Use the Delete page to remove a document from the index along with its source blob, so it no longer appears in chat answers or citations.

## Configuration

Use the Configuration page to review and adjust application settings for the deployment. Among those settings is the orchestrator selector, which chooses how chat answers are produced.

The selector offers the two orchestrators, `agent_framework` and `langgraph`. Switching between them takes effect at runtime, with no redeploy. The value shown by default reflects the deployed default, which follows the `databaseType` choice made at deployment: `postgresql` starts on `langgraph`, and `cosmosdb` starts on `agent_framework`. You can switch to the other orchestrator, and it is served on whichever index store the deployment uses. For the difference between the two, see [Architecture overview](architecture.md#orchestrators).

![Admin site](images/admin-site.png)

The store is fixed at deployment and is not an admin-page choice. The orchestrator, by contrast, is the runtime setting you change on this page. The two together decide the retrieval path: in `cosmosdb` mode the `agent_framework` orchestrator grounds through the Azure AI Foundry knowledge base (Foundry IQ), while every other combination retrieves with app-side search (`BaseSearch.search`). The following diagram traces that flow.

```mermaid
flowchart TD
    Deploy["Deploy time: databaseType / AZURE_ENV_DATABASE_TYPE<br/>fixes the store, cosmosdb or postgresql.<br/>Not selectable on the admin page."]
    Default["Deploy-time default orchestrator, databaseType-derived:<br/>postgresql starts on langgraph, cosmosdb starts on agent_framework"]
    Admin["Admin Configuration page:<br/>select the orchestrator at runtime, no redeploy"]
    Request["Chat request routed to the selected orchestrator"]
    OrchDecision{"Selected orchestrator?"}
    StoreDecision{"Deployed store?"}
    Foundry["Azure AI Foundry knowledge base (Foundry IQ)"]
    AppSearchAF["App-side search, BaseSearch.search"]
    AppSearchLG["App-side search, BaseSearch.search"]

    Deploy --> Default --> Admin --> Request --> OrchDecision
    OrchDecision -->|agent_framework| StoreDecision
    OrchDecision -->|langgraph, either store| AppSearchLG
    StoreDecision -->|cosmosdb| Foundry
    StoreDecision -->|postgresql, pgvector| AppSearchAF
```

## Related documentation

* [App authentication setup](authentication_setup.md)
* [Document ingestion](document_ingestion.md)
* [Supported file types](supported_file_types.md)
