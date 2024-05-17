# Bring your own Data Chat QnA

This sample demonstrates **multi-round** Q&A chatbot powered by GPT. It utilizes indexed files from Azure Machine Learning to provide grounded answers. You can ask a wide range of questions related to Azure Machine Learning and receive responses. The process involves embedding the raw query, using vector search to find most relevant context in user data, and then using GPT to chat with you with the documents. This sample also contains multiple prompt variants that you can tune.

## What you will learn

In this flow, you will learn

* how to compose a multi-round Q&A system flow.
* how to use vector search tool to find relevant documents and leverage domain knowledge.
* how to tune prompt with variants.

## Prerequisites

- Connection: Azure OpenAI or OpenAI connection, with the availability of chat and embedding models/deployments.
- To perform batch run on this sample, you can download the sample data from <a href='https://ragsample.blob.core.windows.net/ragdata/QAGenerationDataChat.jsonl' target='_blank'>here</a>.

## Tools used in this flow

* LLM tool
* Embedding tool
* Vector Index Lookup tool
* Python tool
