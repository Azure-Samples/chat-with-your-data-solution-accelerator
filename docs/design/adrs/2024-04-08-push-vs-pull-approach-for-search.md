Using Push API vs Pull (Integrated Vectorization) technique to index data to Azure Search

* **Status** - proposed
* **Proposer:** @komalgrover
* **Date:** 2024-04-08
* **Technical Story:** [https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator/issues/321](https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator/issues/321)

## Context and Problem Statement

There are two ways to get the data uploaded to the search index i.e using Push based approach or a Pull based approach. This repo is currently using Push based approach in which the developer has more control on how the index is created and what values are put into the index.
We want to add Integrated vectorization (Pull based approach) and allow user to be able to use both the approaches.

## Decision Drivers
* Coexistance of the same index for both the approaches
* Performance
* Complexity - reduces the overhead of chunking & vectorization

## Design Options
* Option 1
Create Azure Blob Datasource, skillset & indexer as part of the infra deployment (thorugh bicep files)
Every time a document is uploaded, indexer can be scheduled to run every 5 min and all the chunking, vectorization process happens internally and data gets indexed.

* Option 2
Create the datasource, skillset, index, indexer when the first document gets uploaded. Can use the create_or_update method for each resource.

In both the above options, the current approach of index creation & index fields will have to be updated, so that the URL embedding feature continues as in using the PUSH based approach.

## Pros and cons of each of the above options

### Option 1
Cons
* Could not find any documentation how can datasource, skillset, indexer can be created thorugh bicep files.
Pros
* One time activity so easier if can be done during initial infra deployment.

### Option 2
Cons
* New helper classes to create resources via REST API
Pros
* Resource creation can be delayed till the time a document is uploaded hence cost effective.

Index fields will need to be updated so that it works for both pull & push based approach.
With the pull based approach in place the azure function will have less load as it will only be responsible for URL embedding.
