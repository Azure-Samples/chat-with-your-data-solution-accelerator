---
title: Document ingestion
description: How Chat with Your Data turns uploaded documents and URLs into a searchable vector index.
ms.date: 2026-07-03
ms.topic: concept
---

[Back to *Chat with your data* README](../README.md)

![Supporting documentation](images/supportingDocuments.png)

## Overview

Ingestion turns your documents into a searchable vector index. When an admin uploads a file or submits a URL, the content is stored, queued, and processed by the ingestion worker, which parses, chunks, embeds, and writes it to the index. The pipeline runs on queues, so large batches process reliably and retry on failure.

## Pipeline

```mermaid
flowchart LR
  UP[Admin uploads doc or URL<br/>frontend admin page] --> BLOB[(Storage blob)]
  BLOB -->|default: direct_enqueue| Q2[[doc-processing queue]]
  BLOB -.optional: event_grid.-> EG[Event Grid] --> Q1[[blob-events queue]]
  Q1 --> BS[batch_start] --> Q2
  ADDURL[add_url] --> Q2
  Q2 --> BP[batch_push<br/>parse, chunk, embed]
  BP --> IDX[(Vector index<br/>AI Search or pgvector)]
  SS[search_skill] --> IDX
```

## Stages

1. **Upload.** An admin uploads a document or submits a URL from the admin pages. Files land in a storage blob; URLs enter the pipeline directly.
2. **Detect.** How a new blob is picked up depends on the `ingestionTrigger` deploy-time setting. By default (`direct_enqueue`), the backend enqueues the document-processing message itself when it writes the blob, with no Event Grid in the path. In the optional `event_grid` mode, a storage Event Grid subscription raises a blob event onto the blob-events queue, which the ingestion worker translates into a processing message.
3. **Batch.** The pipeline expands a blob or batch into per-document work items on the processing queue.
4. **Process.** The ingestion worker parses each document, splits it into chunks, generates embeddings, and writes the chunks to the vector index.
5. **Index.** Processed chunks are written to Azure AI Search in `cosmosdb` mode, or to PostgreSQL with `pgvector` in `postgresql` mode.

## Reliability

The pipeline uses storage queues between stages. If a stage fails, the message is retried, and messages that fail repeatedly move to a poison queue for inspection instead of blocking the batch.

## Supported content

For the file formats you can ingest, see [Supported file types](supported_file_types.md). To add content, see [Admin and configuration](admin.md).

## Related documentation

* [Architecture overview](architecture.md)
* [Admin and configuration](admin.md)
* [Supported file types](supported_file_types.md)
