[Back to *Chat with your data* README](../README.md)

# Integrated Vectorization
[**USER STORY**](#user-story) | [**DEPLOYMENT INSTRUCTIONS**](#local-deployment-instructions)
\
\
![User Story](/media/userStory.png)
## User Story
This feature allows chunking and vectorization of data during ingestion into Azure AI Search through built-in pull-indexers. It supports automatic processing of data directly from storage - meaning the user can just upload their data to Azure Blob Storage and the built-in pull-indexers will do the chunking, vectorization and indexing. This removes the need for Chat With Your Data to explicitly perform chunking, vectorization and pushing to the search index. Read [more](https://learn.microsoft.com/en-us/azure/search/vector-search-integrated-vectorization).

**NOTE**: Every instance of Chat With Your Data will need to be configured whether or not to use Integrated Vectorization at **deployment time**. Once deployed, you will be unable to switch between enabling and disabling Integrated Vectorization when the application is running. In order to run a fresh deployment to switch to and from Integrated Vectorization, refer to the following sections in this document:

* [To switch from Integrated Vectorization disabled to enabled](#local-deployment---if-you-already-have-a-previous-deployment)
* [To switch from Integrated Vectorization enabled to disabled](#local-deployment---if-you-want-to-switch-back-to-push-based-indexing-from-integrated-vectorization)

## Using the Deploy to Azure button
When you click the "Deploy to Azure" button on the repo's main page, you will be taken to the Azure portal, where you can select "true" for the option "Azure Search Use Integrated Vectorization".
![Integrated Vectorization](/media/azure-search-use-iv.png)


## Local Deployment - If deploying for the first time
If you're deploying Chat With Your Data for the first time, run the following before running `azd up` to enable Integrated Vectorization:

```
 azd env set AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION true
```

## Local Deployment - If you already have a previous deployment
If you have previously deployed Chat With Your Data without Integrated Vectorization enabled, you probably have a search index already deployed to your Azure subscription. Integrated Vectorization will require a new, fresh index to function properly so please follow the below steps to enable Integrated Vectorization when you have a previous deployment:

1. On your Azure portal, navigate to the resource group which has your Chat With Your Data deployment.
1. Delete the existing search index.
![Delete Search Index](/media/delete-search-index.png)
1. Run the command `azd env set AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION true`
1. Run `azd up`


## Local Deployment - If you want to switch back to push-based indexing from Integrated Vectorization
If you have a deployment with Integrated Vectorization enabled, and you want to disable it, you will need to follow the below steps:

1. On your Azure portal, navigate to the resource group which has your Chat With Your Data deployment.
1. Delete the existing search index.
![Delete Search Index](/media/delete-search-index.png)
1. Delete the existing indexer.
![Delete Search Index](/media/delete-search-indexer.png)
1. Delete the existing skillset.
![Delete Search Index](/media/delete-search-skillset.png)
1. Delete the existing datasource.
![Delete Search Index](/media/delete-search-datasource.png)
1. Run the command `azd env set AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION false`
1. Run `azd up`
