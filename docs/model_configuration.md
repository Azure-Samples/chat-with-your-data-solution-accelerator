[Back to *Chat with your data* README](../README.md)

# Overview

This document outlines the necessary steps and configurations required for setting up and using models within the solution. It serves as a guide for developers to configure and customize model settings according to the project's needs.

# Model Selection

## Available Models

- For a list of available models, see the [Microsoft Azure AI Services - OpenAI Models documentation](https://learn.microsoft.com/en-us/azure/ai-services/openai/concepts/models).

## Environment Variables (as listed in Azure AI Studio)
- You can access the Environment Variables section of the `LOCAL_DEPLOYMENT.md` file by clicking on this link: [Environment Variables section in LOCAL_DEPLOYMENT.md](LOCAL_DEPLOYMENT.md#environment-variables).

### LLM
- `AZURE_OPENAI_MODEL`: The Azure OpenAI Model Deployment Name
    - example: `my-gpt-4o`
- `AZURE_OPENAI_MODEL_NAME`: The Azure OpenAI Model Name
    - example: `gpt-4o`
- `AZURE_OPENAI_MODEL_VERSION`: The Azure OpenAI Model Version
    - example: `2024-05-13`
- `AZURE_OPENAI_MODEL_CAPACITY`: The Tokens per Minute Rate Limit (thousands)
    - example: `30`

### VISION
- `AZURE_OPENAI_VISION_MODEL`: The Azure OpenAI Model Deployment Name
    - example: `my-gpt-4`
- `AZURE_OPENAI_VISION_MODEL_NAME`: The Azure OpenAI Model Name
    - example: `gpt-4`
- `AZURE_OPENAI_VISION_MODEL_VERSION`: The Azure OpenAI Model Version
    - example: `vision-preview`
- `AZURE_OPENAI_VISION_MODEL_CAPACITY`: The Tokens per Minute Rate Limit (thousands)
    - example: `10`

### EMBEDDINGS
- `AZURE_OPENAI_EMBEDDING_MODEL`: The Azure OpenAI Model Deployment Name
    - example: `my-text-embedding-ada-002`
- `AZURE_OPENAI_EMBEDDING_MODEL_NAME`: The Azure OpenAI Model Name
    - example: `text-embedding-ada-002`
- `AZURE_OPENAI_EMBEDDING_MODEL_VERSION`: The Azure OpenAI Model Version
    - example: `2`
- `AZURE_OPENAI_EMBEDDING_MODEL_CAPACITY`: The Tokens per Minute Rate Limit (thousands)
    - example: `30`
- `AZURE_SEARCH_DIMENSIONS`: Azure OpenAI Embeddings dimensions. A full list of dimensions can be found [here](https://learn.microsoft.com/en-us/azure/ai-services/openai/concepts/models#embeddings-models).
    - example: `1536`

### OPENAI API Configuration
- `AZURE_OPENAI_API_VERSION`: The Azure OpenAI API Version
    - example: `2024-02-01`
- `AZURE_OPENAI_MAX_TOKENS`: The Maximum Tokens per Request
    - example: `1000`
- `AZURE_OPENAI_TEMPERATURE`: The Sampling Temperature (from 0 to 1)
    - example: `0`
- `AZURE_OPENAI_TOP_P`: The Top P Sampling Probability
    - example: `1`

# Model Configuration
- To set an environment variable, you can use the following command:
    - `azd env set <ENVIRONMENT_VARIABLE_NAME> <ENVIRONMENT_VARIABLE_VALUE>`

- To get the value of an environment variable, you can use the following command:
    - `azd env get <ENVIRONMENT_VARIABLE_NAME>`

## GPT-4o & Text-Embeddings-3-Large
- The following environment variables are set for the GPT-4o and Text-Embeddings-3-Large models:
    - `AZURE_OPENAI_API_VERSION`: `2024-05-01-preview`
    - `AZURE_OPENAI_MODEL`: `my-gpt-4o`
    - `AZURE_OPENAI_MODEL_NAME`: `gpt-4o`
    - `AZURE_OPENAI_MODEL_VERSION`: `2024-05-13`
    - `AZURE_OPENAI_EMBEDDING_MODEL`: `my-text-embedding-3-large`
    - `AZURE_OPENAI_EMBEDDING_MODEL_NAME`: `text-embedding-3-large`
    - `AZURE_OPENAI_EMBEDDING_MODEL_VERSION`: `1`
    - `AZURE_SEARCH_DIMENSIONS`: `3072`
    - `AZURE_MAX_TOKENS`: `4096`

---
