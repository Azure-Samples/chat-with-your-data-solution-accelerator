# Use Pull approach(Integrated Vectorization) throughout for ingestion

* **Status** - approved
* **Proposer:** @komalgrover
* **Date:** 2024-04-08
* **Technical Story:** [https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator/issues/321](https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator/issues/321)

## Context and Problem Statement

There are two ways to ingest data to the search index i.e using Push based approach or a Pull based approach. This repository is currently using Push based approach in which the developer has more control on how the index is created and what values are put into the index.
We want to add Integrated vectorization (Pull based approach) and give the flexibility to the user to use either of the two approaches. The purpose of this ADR is to document the approach taken to be able to deploy Pull based approach.

## Requirements
* Demonstrate the usage of Integrated Vectorization (Pull approach)

## Decision Drivers
* Ease of deployment
* Ability to convey the concept of Integrated Vectorization (Pull based approach)
* Clear distinction between Pull & Push approach

## Considered Options
* Using Pull approach throughout
* Using Pull for documents and push for URL embeddings

## Decision outcome
* Using Pull approach throughout, as it meets all our requirements.

## Pros and cons of each of the above options

### Using Pull approach throughout (Resource creation via bicep or code)

Ask the user at the time of deployment on which approach to take. If the user selects Integrated Vectorization(IV), the resources for IV are created during the infra deployment through [bicep](https://learn.microsoft.com/en-us/azure/search/search-get-started-bicep?tabs=CLI) using REST APIs wrapped in script or resources can be created via code when the document gets uploaded to the blob. Once the document is uploaded, the indexer is executed asyncronously which indexes the documents.
In both the options of the resource creation, we still need to have an azure function to index the documents uploaded immediately.
For URL embedding, the URL content is scraped of any html & css related content and the text will be uploaded as a byte stream to the blob storage for further processing. In case the URL content is very large we can handle it by streaming the content in chunks and avoid loading the entire web page content into memory all at once.

With this option in place, we will also be looking if it is possible for anyone to switch between Pull & Push approach.

Cons
* If using Bicep for resource creation: Powershell needs to be installed for the execution of the resource creation script. It is also difficult to create the skillset using Powershell script as it involves setting up mutilple configurable values.
* Effort developing a solution to scrape the url content
* Uploading the content of url as byte stream to the blob storage is a memory overhead.

Pros
* If using code based approach for resource creation: It maintains the same pattern as Push approach of indexing documents when they get uploaded. It is easier to create datasource, indexer, skillset with configurable values.
* Although there is a memory overhead & an effort to build the url scrapper, this option is less confusing as it is easier to maintain a uniform index throughout.
* Very clearly demonstrates the use of Pull based approach.
* Easy to compare the search results between Pull & Push approaches by deploying two separate versions of this repository.

### Using Pull for documents and push for URL embeddings

Ask the user at the time of deployment if they want to go with the Pull approach. The resources for Pull approach get created at the time of deployment. For URL embedding it will continue to use the Push based approach as for URL embedding it is not possible to link the content of URL to the search datasource resource.

Cons
* Difficult to maintain the index as it would contain the URL related data which is indexed through Push and the document data which is using Pull.
* Difficult to compare search results as there is no clear distinction between results from Pull & Push.
* Can be a cause of concern for the end user if they want results only based on Pull approach.

Pros
* No extra effort of building the url scraper.
