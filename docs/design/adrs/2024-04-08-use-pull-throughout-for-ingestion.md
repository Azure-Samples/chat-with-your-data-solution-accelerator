# Use Pull approach(Integrated Vectorization) throughout for ingestion

* **Status** - proposed
* **Proposer:** @komalgrover
* **Date:** 2024-04-08
* **Technical Story:** [https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator/issues/321](https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator/issues/321)

## Context and Problem Statement

There are two ways to ingest data to the search index i.e using Push based approach or a Pull based approach. This repository is currently using Push based approach in which the developer has more control on how the index is created and what values are put into the index.
We want to add Integrated vectorization (Pull based approach) and give the flexibility to the user to use either of the two approaches. The purpose of this ADR is to document the approach taken to be able to deploy Pull based approach.

## Decision Drivers
* Ease of deployment
* Ability to convey the concept of Integrated Vectorization (Pull based approach)

## Considered Options
* Using Pull approach throughout
* Using Pull for documents and push for URL embeddings

## Decision outcome
* Using Pull approach throughout, as it meets all our requirements.

## Pros and cons of each of the above options

### Using Pull approach throughout

Ask the user at the time of deployment on which approach to take. If the user selects Integrated Vectorization(IV), the resources for IV are created during the infra deployment through [bicep](https://learn.microsoft.com/en-us/azure/search/search-get-started-bicep?tabs=CLI) or REST APIs wrapped in script. Indexer can be scheduled to run every 5 min and all the chunking, vectorization process happens internally and data gets indexed.
For URL embedding, the URL content will be downloaded, scraped of any html & css related content and the text will be uploaded to the blob storage for further processing.
With this option in place, we will also be looking if it is possible for anyone to switch between Pull & Push approach.

Cons
* N/A
Pros
* Less confusion, ease of maintaining the index.
* Azure function can be removed as it will no longer be needed to trigger the HTTP phython function.

### Using Pull for documents and push for URL embeddings

Ask the user at the time of deployment if they want to go with the Pull approach. The resources for Pull approach get created at the time of deployment. For URL embedding it will continue to use the Push based approach as for URL embedding it is not possible to link the content of URL to the search datasource resource.

Cons
* Difficult to maintain the index as it would contain the URL related data which is indexed through Push and the document data which is using Pull.
* Additional cost for Azure function as it will only be used for URL embeddings.
* Can be very confusing for the end user.
Pros
* N/A
