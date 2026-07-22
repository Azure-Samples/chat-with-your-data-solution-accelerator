---
title: Employee Assistant
description: Configure and use the employee (HR) assistant persona in Chat with Your Data.
ms.date: 2026-07-03
ms.topic: how-to
---

[Back to *Chat with your data* README](../README.md)

![Supporting documentation](images/supportingDocuments.png)

# Chat With Your Employee Assistant

## Overview
The Chat With Your Employee Assistant is designed to help professionals efficiently navigate their organizations and stay up to date with the latest policies and requirements.

## Employee Assistant Configuration

The following is the Chat With Your Data configuration that we suggest to optimize the performance and functionality of the Employee Assistant:

- **Azure AI Search semantic ranking**: Enable semantic ranking so Azure AI Search surfaces the most relevant handbook and policy passages for each query.
- **Top K 15**: Retrieve the top 15 most relevant chunks so the assistant has enough context to answer precisely without diluting relevance.
- **Azure OpenAI gpt-5.4-mini model**: The solution deploys the Azure OpenAI gpt-5.4-mini model for advanced natural language processing. This model handles nuanced policy questions and produces clear, contextually appropriate responses.

By applying this configuration, you can improve the efficiency, accuracy, and overall performance of the Chat With Your Data Employee Assistant, so it meets the expectations of professionals.

## Updating Configuration Fields

Configure the assistant from the admin **Configuration** page in the web app:

- Set **Assistant Type** to **Employee Assistant** to load the employee persona into the editable answering prompt.
- Enable **semantic search**.
- Set **Top K** to `15`.
- Save the configuration.

The gpt-5.4-mini chat model is selected at deployment time through the `azd` environment, so no runtime change is required.

## Admin Configuration
The admin **Configuration** page includes an **Assistant Type** dropdown. The options are:

- **Default**: the default Chat With Your Data persona.

![UnSelected](images/cwyd_admin_contract_unselected.png)

- **Employee Assistant**: the Employee Assistant persona.

![Checked](images/cwyd_admin_employe_selected.png)

Selecting "Employee Assistant" loads the employee persona into the answering-prompt field, and selecting the default loads the default persona. If you have edited the answering prompt, changing the dropdown overwrites your edits with the selected persona. Ensure you **Save the Configuration** after making this change.

## Employee Assistant Prompt
The employee persona instructs the assistant to act as an HR helper: answer employee policy questions accurately from the retrieved handbook and policy documents, keep a professional and supportive tone, and direct the employee to HR when the answer is not in the documents. The persona carries the behavioral instructions only; the solution injects the retrieved sources and enforces citations automatically.

You can see the [assistant prompt presets](../src/backend/core/agents/assistant_presets.json) file for the full employee persona.

## Sample Employee Policy and Handbook Data
We have added sample employee data in the [data](../data) folder. This data can be used to test and demonstrate the Employee Assistant's capabilities.

## Conclusion
This guide provides an overview of the Chat With Your Data Employee Assistant, how to select its persona from the admin Configuration page, and where the persona is defined. Review the persona and update it per your organizational guidance to maintain consistency and accuracy in responses.

## Related documentation

* [Contract Review and Summarization Assistant](contract_assistance.md)
* [Admin and configuration](admin.md)
* [Supported file types](supported_file_types.md)
