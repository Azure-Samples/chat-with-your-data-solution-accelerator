---
title: Responsible AI FAQ
description: Responsible AI guidance for the Chat with your data Solution Accelerator, covering intended uses, evaluation, and known limitations.
ms.date: 2026-07-03
ms.topic: overview
---

[Back to *Chat with your data* README](../README.md)

![Supporting documentation](images/supportingDocuments.png)

## Overview

Responsible AI guidance for the Chat with your data Solution Accelerator covers its intended uses, how it was evaluated, and its known limitations.

### What is Chat with your data Solution Accelerator?

This solution accelerator is an open-source GitHub repository for the "Chat with your data" solution that combines a retrieval store with the Azure OpenAI GPT-5.1 model to create a conversational search experience. The retrieval store is either Azure AI Search or PostgreSQL with the `pgvector` extension, chosen at deployment time, and retrieval is orchestrated by the configured orchestrator. The solution uses Azure OpenAI GPT and embedding models over an index generated from the customer's data, once installed and deployed, integrated into a web application that provides a natural language interface for search queries. The repository showcases a sample scenario of a contract analyst who wants to review and summarize relevant contracts, and another use case for an employee who wants answers about company policies and benefits.

### What can Chat with your data Solution Accelerator do?

This solution accelerator uses an Azure OpenAI GPT model and an index generated from your data, held in either Azure AI Search or PostgreSQL with the `pgvector` extension, integrated into a web application to provide a natural language interface, including speech-to-text functionality, for search queries.

The sample solution focuses on a contract analyst for contract review and summarization, and an employee assistant for answering questions about company policies and benefits. The sample data is sourced from a select set of publicly available contracts and generated company policy documents. The documents are intended for use as sample data only. The sample solution takes user input in text format and returns LLM responses in text format.

### What is/are Chat with your data Solution Accelerator’s intended use(s)?

This repository is to be used only as a solution accelerator following the open-source license terms listed in the GitHub repository. The example scenario’s intended purpose is to help the identified personas do their work more efficiently.

### How was Chat with your data Solution Accelerator evaluated? What metrics are used to measure performance?

We have run multiple QA passes to evaluate and measure the performance of our accelerator.

### What are the limitations of Chat with your data Solution Accelerator? How can users minimize the impact of Chat with your data Solution Accelerator’s limitations when using the system?

This solution accelerator can only be used as a sample to accelerate the creation of the Chat with your data experience. The repository showcases a sample scenario of a contract analyst and an employee assistant. Users should review the system prompts provided and update as per their organizational guidance. Users should run their own evaluation flow either using the guidance provided in the GitHub repository or their choice of evaluation methods. AI generated content may be inaccurate and should be manually reviewed. Right now, the sample repo is available in English only.

### What operational factors and settings allow for effective and responsible use of Chat with your Data Solution Accelerator?

Users can try different values for some parameters like system prompt, temperature, max tokens etc. shared as configurable environment variables while running run evaluations for AI Assistants. Please note that these parameters are only provided as guidance to start the configuration but not as a complete available list to adjust the system behavior. Please always refer to the latest product documentation for these details or reach out to your Microsoft account team if you need assistance.

## Related documentation

* [Architecture overview](architecture.md)
* [Best practices](best_practices.md)
* [Admin and configuration](admin.md)
