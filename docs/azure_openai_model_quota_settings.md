---
title: Model quota settings
description: Check and adjust Azure AI Foundry model quota for the chat and embedding deployments used by Chat with Your Data.
ms.date: 2026-07-03
ms.topic: how-to
---

[Back to *Chat with your data* README](../README.md)

![Supporting documentation](images/supportingDocuments.png)

## Overview

Chat with Your Data deploys two Azure AI Foundry model deployments: a chat model and an embedding model. Each deployment draws on the quota assigned to your subscription in the deployment region. If quota is short, `azd up` can fail with an `InsufficientQuota` error, so it is worth confirming capacity before you deploy and adjusting it afterward.

The default deployments are:

| Purpose | Model | Deployment type | Default capacity (TPM, thousands) |
|---------|-------|-----------------|-----------------------------------|
| Chat | `gpt-5.1` | GlobalStandard | 150 |
| Embeddings | `text-embedding-3-large` | Standard | 100 |

You can change the model, version, deployment type, and capacity through azd parameters. See [Model configuration](model_configuration.md) and [Customizing azd parameters](customizing_azd_parameters.md).

## Check quota before deploying

Follow the [quota check guide](QuotaCheck.md) to confirm capacity by region before you run `azd up`.

## Check and update quota in the portal

1. Sign in to the [Azure AI Foundry portal](https://ai.azure.com/).
2. Select **View all resources** and find the Azure AI Services resource for this deployment.
3. Open **Quota** from the management section.
4. Select the deployment type (for example, **GlobalStandard**) from the dropdown.
5. Choose the model (the chat model `gpt-5.1` or the embedding model `text-embedding-3-large`) and the region where you deployed.
6. Request more quota, or delete unused model deployments to free capacity.

## Adjust capacity through azd

To change a deployment's capacity, set the matching azd parameter before you deploy:

```bash
azd env set AZURE_ENV_GPT_MODEL_CAPACITY 200
azd env set AZURE_ENV_EMBEDDING_MODEL_CAPACITY 150
azd up
```

## Related documentation

* [Check quota by region](QuotaCheck.md)
* [Model configuration](model_configuration.md)
* [Customizing azd parameters](customizing_azd_parameters.md)
