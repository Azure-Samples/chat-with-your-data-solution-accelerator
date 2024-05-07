[Back to *Chat with your data* README](../README.md)

# Integrated Vectorization
[**USER STORY**](#user-story) | [**DEPLOYMENT INSTRUCTIONS**](#local-deployment-instructions)
\
\
![User Story](/media/userStory.png)
## User Story
This feature allows chunking and vectorization of data during ingestion into Azure AI Search through built-in pull-indexers. It supports automatic processing of data directly from storage - meaning the user can just upload their data to Azure Blob Storage and the built-in pull-indexers will do the chunking, vectorization and indexing. This removes the need for Chat With Your Data to explicitly perform chunking, vectorization and pushing to the search index.

## Local Deployment Instructions
In addition to the standard local deployment instructions, do the following to enable Integrated Vectorization:

* Run `azd env set AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION true` before running `azd up`.
