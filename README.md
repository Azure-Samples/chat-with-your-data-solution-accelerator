# "Chat with your data" Solution Accelerator  
  
Welcome to the "Chat with your data" Solution Accelerator repository! 

The "Chat with your data" Solution Accelerator is a powerful tool that combines the capabilities of Azure Cognitive Search and GPT language model to create a conversational search experience. The solution accelerator includes ChatGPT model and a search index generated from your data, which can be integrated into a web application to provide users with a natural language interface for search queries.

This repository provides a template for setting up the solution accelerator, along with detailed instructions on how to use and customize it to fit your specific needs.


## When should you use this repo? 

*If you are looking to implement the RAG (Retrieval Augmented Generation) pattern and chat with your enterprise data, Microsoft built-in and recommended product for this is here: [Azure OpenAI Service on your data][../azure/cognitive-services/openai/use-your-data-quickstart]. If there is any functionality that you require that is still not available in the product, follow up with [Azure OpenAI Service on your data contact](emailto:wedne_support@microsoft.com) for feedback and to understand your business need.*

In case your setup requires more customization than what is currently available out-of-the-box with [Azure OpenAI Service on your data][../azure/cognitive-services/openai/use-your-data-quickstart], this is the repo for you!

*Have you seen [ChatGPT + Enterprise data with Azure OpenAI and Cognitive Search demo](https://github.com/Azure-Samples/azure-search-openai-demo)? If you would like to play with prompts, understanding RAG pattern different implementation approaches and similar demo tasks, that is your repo!*

If you would like to create a POC [Proof of Concept] and customize to your own business needs and understand best practices, this is the repo for you!

## Getting Started

To get this deployed directly in your Azure Subscription follow these steps:

### Prerequisites

- Azure Subscription with Contributor access
- Azure OpenAI resource


### Quickstart

 [![Deploy to Azure](https://aka.ms/deploytoazurebutton)]() 
1. Click on the Deploy to Azure button and configure your settings in the Azure Portal as described in the [Environment variables section](#environment-variables).
The button will work when the repo goes public, please copy past the ARM template in the infrastructure folder and follow these [instructions](https://learn.microsoft.com/en-us/azure/azure-resource-manager/templates/quickstart-create-templates-use-the-portal).
2. Navigate to the Admin
    - TO DO: Add a picture here
3. Upload documents
4. Navigate to the Web App and "Chat with your data"

## Features

This project framework provides the following features:

* Chat with your own data
* Upload and process your documents
* Index public web pages
* Easy prompt configuration
* Multiple chunking strategies


## Development 
### Runnind the solution locally
You can run the full solution locally with the following commands.
It will spin up 3 different docker containers for the:
- Frontend
- Backend
- BatchProcessing

```shell
cd docker
docker compose up
```
### Develop Frontend
#### Running the frontend locally:
- python -m pip install -r requirements.txt
- cd frontend
- npm install
- npm run build
- python ./app.py

#### Docker image
```shell
docker build -f docker\WebApp.Dockerfile -t YOUR_DOCKER_REGISTRY/YOUR_DOCKER_IMAGE .
docker run --env-file .env -p 8080:80 YOUR_DOCKER_REGISTRY/YOUR_DOCKER_IMAGE
docker push YOUR_DOCKER_REGISTRY/YOUR_DOCKER_IMAGE
```

### Develop Backend
#### Running the backend locally:
- cd backend
- python -m pip install -r requirements.txt
- streamlit run Admin.py

#### Docker image
```shell
docker build -f docker\AdminWebApp.Dockerfile -t YOUR_DOCKER_REGISTRY/YOUR_DOCKER_IMAGE .
docker run --env-file .env -p 8081:80 YOUR_DOCKER_REGISTRY/YOUR_DOCKER_IMAGE
docker push YOUR_DOCKER_REGISTRY/YOUR_DOCKER_IMAGE
```

### Develop Batch processing
#### Running the batch processing
- Install [Azure Functions Core Tools](https://learn.microsoft.com/en-us/azure/azure-functions/functions-run-local?tabs=windows%2Cportal%2Cv2%2Cbash&pivots=programming-language-python)
- cd backend
- func start or Use the [Azure Functions VS Code extension](https://marketplace.visualstudio.com/items?itemName=ms-azuretools.vscode-azurefunctions)

#### Docker image
```shell
docker build -f docker\Backend.Dockerfile -t YOUR_DOCKER_REGISTRY/YOUR_DOCKER_IMAGE .
docker run --env-file .env -p 7071:80 YOUR_DOCKER_REGISTRY/YOUR_DOCKER_IMAGE
docker push YOUR_DOCKER_REGISTRY/YOUR_DOCKER_IMAGE
```

## Environment variables

| App Setting | Value | Note |
| --- | --- | ------------- |
|AZURE_SEARCH_SERVICE||The name of your Azure Cognitive Search resource|
|AZURE_SEARCH_INDEX||The name of your Azure Cognitive Search Index|
|AZURE_SEARCH_KEY||An **admin key** for your Azure Cognitive Search resource|
|AZURE_SEARCH_USE_SEMANTIC_SEARCH|False|Whether or not to use semantic search|
|AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG||The name of the semantic search configuration to use if using semantic search.|
|AZURE_SEARCH_TOP_K|5|The number of documents to retrieve from Azure Cognitive Search.|
|AZURE_SEARCH_ENABLE_IN_DOMAIN|True|Limits responses to only queries relating to your data.|
|AZURE_SEARCH_CONTENT_COLUMNS||List of fields in your Azure Cognitive Search index that contains the text content of your documents to use when formulating a bot response. Represent these as a string joined with "|", e.g. `"product_description|product_manual"`|
|AZURE_SEARCH_FILENAME_COLUMN||`AZURE_SEARCH_FILENAME_COLUMN`: Field from your Azure Cognitive Search index that gives a unique idenitfier of the source of your data to display in the UI.|
|AZURE_SEARCH_TITLE_COLUMN||Field from your Azure Cognitive Search index that gives a relevant title or header for your data content to display in the UI.|
|AZURE_SEARCH_URL_COLUMN||Field from your Azure Cognitive Search index that contains a URL for the document, e.g. an Azure Blob Storage URI. This value is not currently used.|
|AZURE_OPENAI_RESOURCE||the name of your Azure OpenAI resource|
|AZURE_OPENAI_MODEL||The name of your model deployment|
|AZURE_OPENAI_MODEL_NAME|gpt-35-turbo|The name of the model|
|AZURE_OPENAI_KEY||One of the API keys of your Azure OpenAI resource|
|AZURE_OPENAI_EMBEDDING_MODEL|text-embedding-ada-002|The name of you Azure OpenAI embeddings model deployment|
|AZURE_OPENAI_TEMPERATURE|0|What sampling temperature to use, between 0 and 2. Higher values like 0.8 will make the output more random, while lower values like 0.2 will make it more focused and deterministic. A value of 0 is recommended when using your data.|
|AZURE_OPENAI_TOP_P|1.0|An alternative to sampling with temperature, called nucleus sampling, where the model considers the results of the tokens with top_p probability mass. We recommend setting this to 1.0 when using your data.|
|AZURE_OPENAI_MAX_TOKENS|1000|The maximum number of tokens allowed for the generated answer.|
|AZURE_OPENAI_STOP_SEQUENCE||Up to 4 sequences where the API will stop generating further tokens. Represent these as a string joined with "|", e.g. `"stop1|stop2|stop3"`|
|AZURE_OPENAI_SYSTEM_MESSAGE|You are an AI assistant that helps people find information.|A brief description of the role and tone the model should use|
|AZURE_OPENAI_API_VERSION|2023-06-01-preview|API version when using Azure OpenAI on your data|
|AzureWebJobsStorage||The connection string to the Azure Blob Storage for the Azure Functions Batch processing|
|BACKEND_URL||The URL for the Backend Batch Azure Function. Use http://localhost:7071 for local execution and http://backend for docker compose|
|DOCUMENT_PROCESSING_QUEUE_NAME|doc-processing|The name of the Azure Queue to handle the Batch processing|
|AZURE_BLOB_ACCOUNT_NAME||The name of the Azure Blob Storage for storing the original documents to be processed|
|AZURE_BLOB_ACCOUNT_KEY||The key of the Azure Blob Storage for storing the original documents to be processed|
|AZURE_BLOB_CONTAINER_NAME||The name of the Container in the Azure Blob Storage for storing the original documents to be processed|
|AZURE_FORM_RECOGNIZER_ENDPOINT||The name of the Azure Form Recognizer for extracting the text from the documents|
|AZURE_FORM_RECOGNIZER_KEY||The key of the Azure Form Recognizer for extracting the text from the documents|
|APPINSIGHTS_CONNECTION_STRING||The Application Insights connection string to store the application logs|

## How to extend the project
### Class description
### Module logic

## Demo

A demo app is included to show how to use the project.

To run the demo, follow these steps:

(Add steps to start up the demo)

1.
2.
3.

## Resources

(Any additional resources or related projects)

- Link to supporting information
- Link to similar sample
- ...

## Licensing

This repository is licensed under the [MIT License](LICENSE.md).

The data set under the /data folder is licensed under the [CDLA-Permissive-2 License](CDLA-Permissive-2.md).

## Data Set

The data set under the /data folder has been generated with Azure OpenAI GPT and DALL-E 2 models.


# DISCLAIMER
This presentation, demonstration, and demonstration model are for informational purposes only and (1) are not subject to SOC 1 and SOC 2 compliance audits, and (2) are not designed, intended or made available as a medical device(s) or as a substitute for professional medical advice, diagnosis, treatment or judgment. Microsoft makes no warranties, express or implied, in this presentation, demonstration, and demonstration model. Nothing in this presentation, demonstration, or demonstration model modifies any of the terms and conditions of Microsoft’s written and signed agreements. This is not an offer and applicable terms and the information provided are subject to revision and may be changed at any time by Microsoft.

This presentation, demonstration, and demonstration model do not give you or your organization any license to any patents, trademarks, copyrights, or other intellectual property covering the subject matter in this presentation, demonstration, and demonstration model.

The information contained in this presentation, demonstration and demonstration model represents the current view of Microsoft on the issues discussed as of the date of presentation and/or demonstration, for the duration of your access to the demonstration model. Because Microsoft must respond to changing market conditions, it should not be interpreted to be a commitment on the part of Microsoft, and Microsoft cannot guarantee the accuracy of any information presented after the date of presentation and/or demonstration and for the duration of your access to the demonstration model.

No Microsoft technology, nor any of its component technologies, including the demonstration model, is intended or made available as a substitute for the professional advice, opinion, or judgment of (1) a certified financial services professional, or (2) a certified medical professional. Partners or customers are responsible for ensuring the regulatory compliance of any solution they build using Microsoft technologies.
