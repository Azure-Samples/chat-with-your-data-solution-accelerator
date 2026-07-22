---
title: Contract Review and Summarization Assistant
description: Configure and use the contract review persona in Chat with Your Data.
ms.date: 2026-07-03
ms.topic: how-to
---

[Back to *Chat with your data* README](../README.md)

![Supporting documentation](images/supportingDocuments.png)

# Chat With Your Data Contract Review and Summarization Assistant

## Overview
The Chat With Your Data Contract Review and Summarization Assistant is designed to help professionals efficiently manage and interact with a large collection of documents. It utilizes advanced natural language processing capabilities to provide accurate and contextually relevant responses to user queries about the documents.

## Contract Review and Summarization Assistant Configuration

The following is the Chat With Your Data configuration that we suggest to optimize the performance and functionality of the Contract Review and Summarization Assistant:

- **Azure AI Search semantic ranking**: Enable semantic ranking so Azure AI Search surfaces the most relevant contract passages for each query.
- **Top K 15**: Retrieve the top 15 most relevant chunks so the assistant has enough context to answer precisely without diluting relevance.
- **Azure OpenAI gpt-5.4-mini model**: The solution deploys the Azure OpenAI gpt-5.4-mini model for advanced natural language processing. This model handles complex legal queries and produces detailed, contextually appropriate responses.

By applying this configuration, you can improve the efficiency, accuracy, and overall performance of the Chat With Your Data Contract Review and Summarization Assistant, so it meets the expectations of professionals.

## Updating Configuration Fields

Configure the assistant from the admin **Configuration** page in the web app:

- Set **Assistant Type** to **Contract Assistant** to load the contract persona into the editable answering prompt.
- Enable **semantic search**.
- Set **Top K** to `15`.
- Save the configuration.

The gpt-5.4-mini chat model is selected at deployment time through the `azd` environment, so no runtime change is required.

## Admin Configuration
The admin **Configuration** page includes an **Assistant Type** dropdown. The options are:

- **Default**: the default Chat With Your Data persona.

![UnSelected](images/cwyd_admin_contract_unselected.png)

- **Contract Assistant**: the Contract Review and Summarization Assistant persona.

![Checked](images/cwyd_admin_contract_selected.png)

Selecting "Contract Assistant" loads the contract persona into the answering-prompt field, and selecting the default loads the default persona. If you have edited the answering prompt, changing the dropdown overwrites your edits with the selected persona. Ensure you **Save the Configuration** after making this change.

## Contract Review and Summarization Assistant Prompt
The contract persona instructs the assistant to answer from the retrieved documents, list documents as a table, and summarize each contract with a consistent shape: parties, key dates, obligations, and terms. The persona carries the behavioral instructions only; the solution injects the retrieved sources and enforces citations automatically.

You can see the [assistant prompt presets](../src/backend/core/agents/assistant_presets.json) file for the full contract persona.

## Sample Contract Data
We have added sample contract data in the [Contract Assistant sample docs](../data/contract_data) folder. This data can be used to test and demonstrate the Contract Review and Summarization Assistant's capabilities.

## Conclusion
This guide provides an overview of the Chat With Your Data Contract Review and Summarization Assistant, how to select its persona from the admin Configuration page, and where the persona is defined. Review the persona and update it per your organizational guidance to maintain consistency and accuracy in responses.

## Related documentation

* [Employee Assistant](employee_assistance.md)
* [Admin and configuration](admin.md)
* [Supported file types](supported_file_types.md)
