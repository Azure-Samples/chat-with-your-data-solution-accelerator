[Back to *Chat with your data* README](../README.md)

## Local deployment

To customize the accelerator or run it locally, first, copy the `.env.sample` file to your development environment's `.env` file, and edit it according to [environment variable values table](#environment-variables) below.

### Authenticate using RBAC
To authenticate using API Keys, update the value of `AZURE_AUTH_TYPE` to keys. For accessing using 'rbac', manually make changes by following the below steps:
1. Ensure role assignments listed on [this page](https://techcommunity.microsoft.com/t5/ai-azure-ai-services-blog/eliminate-dependency-on-key-based-authentication-in-azure/ba-p/3821880) 
have been created.
2. Navigate to your Search service in the Azure Portal
3. Under Settings, select `Keys`
4. Select either `Role-based access control` or `Both`
5. Navigate to your App service in the Azure Portal
6. Under Settings, select `Configuration`
7. Set the value of the `AZURE_AUTH_TYPE` setting to `rbac`
8. Restart the application

### Running the full solution locally with Docker Compose

You can run the full solution locally with the following commands - this will spin up 3 different Docker containers:

|Container  |Description  |
|---------|---------|
|webapp | A container for the chat app, enabling you to chat on top of your data.         |
|admin webapp     | A container for the "admin" site where you can upload and explore your data.         |
|batch processing functions     | A container helping with processing requests.          |

Run the following `docker compose` command.

```shell
cd docker
docker compose up
```

### Develop & run the frontend locally

For faster development, you can run the frontend Typescript React UI app and the Python Flask api app in development mode. This allows the app to "hot reload" meaning your changes will automatically be reflected in the app without having to refresh or restart the local servers.

They can be launched locally from vscode (Ctrl+Shift+D) and selecting "Launch Frontend (api)" and "Launch Frontend (UI). You will also be able to place breakpoints in the code should you wish. This will automatically install any dependencies for Node and Python.

#### Starting the Flask app in dev mode from the command line (optional)
This step is included if you cannot use the Launch configuration in VSCode. Open a terminal and enter the following commands
```shell
cd code
python -m pip install -r requirements.txt
cd app
python -m flask --app ./app.py --debug run
```

#### Starting the Typescript React app in dev mode (optional)
This step is included if you cannot use the Launch configuration in VSCode. Open a new separate terminal and enter the following commands:
```shell
cd code\app\frontend
npm install
npm run dev
```
The local vite server will return a url that you can use to access the chat interface locally, such as  `http://localhost:5174/`.

#### Building the user app Docker image

```shell
docker build -f docker\WebApp.Dockerfile -t YOUR_DOCKER_REGISTRY/YOUR_DOCKER_IMAGE .
docker run --env-file .env -p 8080:80 YOUR_DOCKER_REGISTRY/YOUR_DOCKER_IMAGE
docker push YOUR_DOCKER_REGISTRY/YOUR_DOCKER_IMAGE
```

### Develop & run the admin app

The admin app can be launched locally from vscode (Ctrl+Shift+D) and selecting "Launch Admin site". You will also be able to place breakpoints in the Python Code should you wish.

This should automatically open `http://localhost:8501/` and render the admin interface.

#### Building the backend Docker image

```shell
docker build -f docker\AdminWebApp.Dockerfile -t YOUR_DOCKER_REGISTRY/YOUR_DOCKER_IMAGE .
docker run --env-file .env -p 8081:80 YOUR_DOCKER_REGISTRY/YOUR_DOCKER_IMAGE
docker push YOUR_DOCKER_REGISTRY/YOUR_DOCKER_IMAGE
```

**NOTE**: If you are using Linux, make sure to go to https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator/blob/main/docker/docker-compose.yml#L9 and modify the docker-compose.yml to use forward slash /. The backslash version just works with Windows.


### Develop & run the batch processing functions

If you want to develop and run the batch processing functions container locally, use the following commands.

#### Running the batch processing locally

First, install [Azure Functions Core Tools](https://learn.microsoft.com/en-us/azure/azure-functions/functions-run-local?tabs=windows%2Cportal%2Cv2%2Cbash&pivots=programming-language-python).

```shell
cd code\batch
func start
```

Or use the [Azure Functions VS Code extension](https://marketplace.visualstudio.com/items?itemName=ms-azuretools.vscode-azurefunctions).

#### Debugging the batch processing functions locally
Rename the file `local.settings.json.sample` in the `batch` folder to `local.settings.json` and update the `AzureWebJobsStorage` value with the storage account connection string.

Execute the above [shell command](#L81) to run the function locally. You may need to stop the deployed function on the portal so that all requests are debugged locally.

#### Building the batch processing Docker image

```shell
docker build -f docker\Backend.Dockerfile -t YOUR_DOCKER_REGISTRY/YOUR_DOCKER_IMAGE .
docker run --env-file .env -p 7071:80 YOUR_DOCKER_REGISTRY/YOUR_DOCKER_IMAGE
docker push YOUR_DOCKER_REGISTRY/YOUR_DOCKER_IMAGE
```

## Environment variables

| App Setting | Value | Note |
| --- | --- | ------------- |
|AZURE_SEARCH_SERVICE||The URL of your Azure AI Search resource. e.g. https://<search-service>.search.windows.net|
|AZURE_SEARCH_INDEX||The name of your Azure AI Search Index|
|AZURE_SEARCH_KEY||An **admin key** for your Azure AI Search resource|
|AZURE_SEARCH_USE_SEMANTIC_SEARCH|False|Whether or not to use semantic search|
|AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG||The name of the semantic search configuration to use if using semantic search.|
|AZURE_SEARCH_TOP_K|5|The number of documents to retrieve from Azure AI Search.|
|AZURE_SEARCH_ENABLE_IN_DOMAIN|True|Limits responses to only queries relating to your data.|
|AZURE_SEARCH_CONTENT_COLUMNS||List of fields in your Azure AI Search index that contains the text content of your documents to use when formulating a bot response. Represent these as a string joined with "|", e.g. `"product_description|product_manual"`|
|AZURE_SEARCH_CONTENT_VECTOR_COLUMNS||Field from your Azure AI Search index for storing the content's Vector embeddings|
|AZURE_SEARCH_DIMENSIONS|1536| Azure OpenAI Embeddings dimensions. 1536 for `text-embedding-ada-002`|
|AZURE_SEARCH_FIELDS_ID|id|`AZURE_SEARCH_FIELDS_ID`: Field from your Azure AI Search index that gives a unique idenitfier of the document chunk. `id` if you don't have a specific requirement.|
|AZURE_SEARCH_FILENAME_COLUMN||`AZURE_SEARCH_FILENAME_COLUMN`: Field from your Azure AI Search index that gives a unique idenitfier of the source of your data to display in the UI.|
|AZURE_SEARCH_TITLE_COLUMN||Field from your Azure AI Search index that gives a relevant title or header for your data content to display in the UI.|
|AZURE_SEARCH_URL_COLUMN||Field from your Azure AI Search index that contains a URL for the document, e.g. an Azure Blob Storage URI. This value is not currently used.|
|AZURE_SEARCH_FIELDS_TAG|tag|Field from your Azure AI Search index that contains tags for the document. `tag` if you don't have a specific requirement.|
|AZURE_SEARCH_FIELDS_METADATA|metadata|Field from your Azure AI Search index that contains metadata for the document. `metadata` if you don't have a specific requirement.|
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
|ORCHESTRATION_STRATEGY | openai_functions | Orchestration strategy. Use Azure OpenAI Functions (openai_functions) or LangChain (langchain) for messages orchestration. If you are using a new model version 0613 select "openai_functions" (or "langchain"), if you are using a 0314 model version select "langchain" |
|AZURE_CONTENT_SAFETY_ENDPOINT | | The endpoint of the Azure AI Content Safety service |
|AZURE_CONTENT_SAFETY_KEY | | The key of the Azure AI Content Safety service|
|AZURE_SPEECH_SERVICE_KEY | | The key of the Azure Speech service|
|AZURE_SPEECH_SERVICE_REGION | | The region (location) of the Azure Speech service|
|AZURE_AUTH_TYPE | rbac | Change the value to 'keys' to authenticate using AZURE API keys. For more information refer to section [Authenticate using RBAC](#authenticate-using-rbac)
