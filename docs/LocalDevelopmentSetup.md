# Local Development Setup Guide
This guide provides comprehensive instructions for setting up the Chat With You Data Solution Accelerator for local development across Windows, Linux and MacOS platforms.

## Important Setup Notes

### Multi-Service Architecture

This application consists of **three separate services** that run independently:

1. **Frontend**
2. **Admin web**
3. **Batch processing function**

> **⚠️ Critical: Each service must run in its own terminal/console window**
>
> - **Do NOT close terminals** while services are running
> - Open **4 separate terminal windows** for local development
> - Each service will occupy its terminal and show live logs



## Local debugging

To customize the accelerator or run it locally, you must provision the Azure resources by running `azd provision` in a Terminal. This will generate a `.env` for you and you can use the "Run and Debug" (Ctrl + Shift + D) command to chose which part of the accelerator to run.  There is an [environment variable values table](#environment-variables) below.


To run the accelerator in local when the solution is secured by RBAC you need to assign some roles to your principal id. You can do it either manually or Programmatically.

### Manually assign roles
You need to assign the following roles to your `PRINCIPALID` (you can get your 'principal id' from Microsoft Entra ID):

| Role | GUID |
|----|----|
| Cognitive Services OpenAI User | 5e0bd9bd-7b93-4f28-af87-19fc36ad61bd |
| Cognitive Services User | a97b65f3-24c7-4388-baec-2e87135dc908 |
| Cosmos DB SQL Data Contributor | 00000000-0000-0000-0000-000000000002 ([How to assign](https://learn.microsoft.com/en-us/azure/cosmos-db/how-to-setup-rbac#role-assignments)) |
| Key Vault Secrets User | 4633458b-17de-408a-b874-0445c86b69e6 |
| Search Index Data Contributor | 8ebe5a00-799e-43f5-93ac-243d3dce84a7 |
| Search Service Contributor | 7ca78c08-252a-4471-8644-bb5ff32d4ba0 |
| Storage Blob Data Contributor | ba92f5b4-2d11-453d-a403-e96b0029c9fe |
| Storage Queue Data Contributor | 974c5e8b-45b9-4653-ba55-5f855dd0fb88 |

### Programmatically assign roles
You can also update the `principalId` value with your own principalId in the `main.bicep` file.
Refer this section [Assign roles using cmd](#step-8-assigning-azure-roles-using-command-line)

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

### Deploy services manually

You can deploy the full solution from local with the following command `azd deploy`. You can also deploy services individually

|Service  |Description  |
|---------|---------|
|`azd deploy web` | A python app, enabling you to chat on top of your data.         |
|`azd deploy adminweb`     | A Streamlit app for the "admin" site where you can upload and explore your data.         |
|`azd deploy function`     | A python function app processing requests.          |

### Running All Services Locally Using Docker Compose

To run all applications using Docker Compose, you first need a `.env` file containing the configuration for your
provisioned resources. This file can be created manually at the root of the project. Alternatively, if resources were
provisioned using `azd provision` or `azd up`, a `.env` file is automatically generated in the `.azure/<env-name>/.env`
file. To get your `<env-name>` run `azd env list` to see which env is default.

Set APP_ENV in your `.env` file to control Azure authentication. Set the environment variable to dev to use Azure CLI credentials, or to prod to use Managed Identity for production. Ensure you're logged in via az login when using dev in local. To configure your environment, ensure that APP_ENV is set to **"dev"** in your .env file.

The `AzureWebJobsStorage` needs to be added to your `.env` file manually. This can be retrieved from the function
settings via the Azure Portal.

To start the services, you can use either of the following commands:
- `make docker-compose-up`
- `cd docker && AZD_ENV_FILE=<path-to-env-file> docker-compose up`

**Note:** By default, these commands will run the latest Docker images built from the main branch. If you wish to use a
different image, you will need to modify the `docker/docker-compose.yml` file accordingly.

## Step 1: Prerequisites - Install Required Tools
-	Code Editor: Visual Studio Code
-	Extensions: Azure Functions, Azure Tools, Bicep, Pylance, Python, Teams Toolkit (Optional)
-	Python: Version 3.11
-	Node.js: LTS version
-	Azure Developer CLI (azd)
-	Azure Functions Core Tools

## Step 2: Clone the Repository

```bash
git clone https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator.git
cd chat-with-your-data-solution-accelerator
```

## Step 3: Set Up Python Virtual Environment

#### Option 1: Windows (PowerShell)
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```
#### Option 2: Linux/macOS
```bash
python3 -m venv .venv
source .venv/bin/activate
```

## Step 4: Install Python Dependencies

Run inside `backend, batch and utilities` folders:
```powershell
pip install --upgrade pip
pip install poetry
poetry export -o requirements.txt
pip install -r requirements.txt
```
Alternative: Run the setup script
```powershell
.devcontainer/setupEnv.sh
```

## Step 5: Develop & run the frontend locally

For faster development, you can run the frontend Typescript React UI app and the Python Flask api app in development mode. This allows the app to "hot reload" meaning your changes will automatically be reflected in the app without having to refresh or restart the local servers.

They can be launched locally from vscode (Ctrl+Shift+D) and selecting "Launch Frontend (api)" and "Launch Frontend (UI). You will also be able to place breakpoints in the code should you wish. This will automatically install any dependencies for Node and Python.


#### Starting the Flask app in dev mode from the command line (optional)
This step is included if you cannot use the Launch configuration in VSCode. Open a terminal and enter the following commands
```shell
cd code
poetry run flask run
```
You will get Flask API URL, default: `http://127.0.0.1:5050`

Update `vite.config.ts` to point API URL: `http://127.0.0.1:5050`

#### Starting the Typescript React app in dev mode (optional)
This step is included if you cannot use the Launch configuration in VSCode. Open a new separate terminal and enter the following commands:
```shell
cd code\frontend
npm install
npm run dev
```
The local vite server will return a url that you can use to access the chat interface locally, such as  `http://localhost:5174/`.

## Step 6: Develop & run the admin app

The admin app can be launched locally from vscode (Ctrl+Shift+D) and selecting "Launch Admin site". You will also be able to place breakpoints in the Python Code should you wish.

This should automatically open `http://localhost:8501/` and render the admin interface.

Command Line (Optional):
```powershell
cd code/backend
streamlit run admin.py
```

## Step 7: Develop & run the batch processing functions

If you want to develop and run the batch processing functions container locally, use the following commands.

#### Running the batch processing locally

First, install [Azure Functions Core Tools](https://learn.microsoft.com/en-us/azure/azure-functions/functions-run-local?tabs=windows%2Cportal%2Cv2%2Cbash&pivots=programming-language-python).

```shell
cd code\backend\batch
poetry run func start
```

Or use the [Azure Functions VS Code extension](https://marketplace.visualstudio.com/items?itemName=ms-azuretools.vscode-azurefunctions).

#### Debugging the batch processing functions locally
Rename the file `local.settings.json.sample` in the `batch` folder to `local.settings.json` and update the `AzureWebJobsStorage__accountName` value with the storage account name.

Copy the .env file from [previous section](#local-debugging) to the `batch` folder.

Execute the steps in [Running the batch processing locally](#running-the-batch-processing-locally) to run the function locally. You may need to stop the deployed function on the portal so that all requests are debugged locally. To trigger the function, you can click on the corresponding URL that will be printed to the terminal.

## Step 8: Assigning Azure Roles using command line

Replace with your actual IDs and run:

```sh
#!/bin/bash

# Variables - Update these with your values
SUBSCRIPTION_ID="<your-subscription-id>"
RESOURCE_GROUP="<your-resource-group>"
PRINCIPAL_ID="<user-or-service-principal-id>"
SOLUTION_PREFIX="<your-solution-prefix>"

# Azure AI Search (CosmosDB deployments only)
az role assignment create --assignee $PRINCIPAL_ID --role "Search Index Data Contributor" --scope /subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Search/searchServices/srch-$SOLUTION_PREFIX
az role assignment create --assignee $PRINCIPAL_ID --role "Search Service Contributor" --scope /subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Search/searchServices/srch-$SOLUTION_PREFIX
az role assignment create --assignee $PRINCIPAL_ID --role "Search Index Data Reader" --scope /subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Search/searchServices/srch-$SOLUTION_PREFIX

# Azure OpenAI
az role assignment create --assignee $PRINCIPAL_ID --role "Cognitive Services User" --scope /subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.CognitiveServices/accounts/oai-$SOLUTION_PREFIX
az role assignment create --assignee $PRINCIPAL_ID --role "Cognitive Services OpenAI User" --scope /subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.CognitiveServices/accounts/oai-$SOLUTION_PREFIX

# Computer Vision (if enabled)
az role assignment create --assignee $PRINCIPAL_ID --role "Cognitive Services User" --scope /subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.CognitiveServices/accounts/cv-$SOLUTION_PREFIX

# Speech Services
az role assignment create --assignee $PRINCIPAL_ID --role "Cognitive Services User" --scope /subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.CognitiveServices/accounts/spch-$SOLUTION_PREFIX

# Document Intelligence
az role assignment create --assignee $PRINCIPAL_ID --role "Cognitive Services User" --scope /subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.CognitiveServices/accounts/di-$SOLUTION_PREFIX

# Content Safety
az role assignment create --assignee $PRINCIPAL_ID --role "Cognitive Services User" --scope /subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.CognitiveServices/accounts/cs-$SOLUTION_PREFIX

# Storage Account
az role assignment create --assignee $PRINCIPAL_ID --role "Storage Blob Data Contributor" --scope /subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Storage/storageAccounts/st$SOLUTION_PREFIX
az role assignment create --assignee $PRINCIPAL_ID --role "Storage Queue Data Contributor" --scope /subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Storage/storageAccounts/st$SOLUTION_PREFIX

# Key Vault
az role assignment create --assignee $PRINCIPAL_ID --role "Key Vault Secrets User" --scope /subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.KeyVault/vaults/kv-$SOLUTION_PREFIX

# Cosmos DB (if using CosmosDB)
az cosmosdb sql role assignment create --account-name cosmos-$SOLUTION_PREFIX --resource-group $RESOURCE_GROUP --scope "/" --principal-id $PRINCIPAL_ID --role-definition-id 00000000-0000-0000-0000-000000000002

# Add user as PostgreSQL administrator

```

## Environment variables

| App Setting | Value | Note |
| --- | --- | ------------- |
|ADVANCED_IMAGE_PROCESSING_MAX_IMAGES | 1 | The maximum number of images to pass to the vision model in a single request|
|APPLICATIONINSIGHTS_CONNECTION_STRING||The Application Insights connection string to store the application logs|
|APP_ENV | Prod | Application Environment (Prod, Dev, etc.)|
|AZURE_AUTH_TYPE | keys | The default is to use API keys. Change the value to 'rbac' to authenticate using Role Based Access Control. For more information refer to section [Authenticate using RBAC](#authenticate-using-rbac)|
|AZURE_BLOB_ACCOUNT_KEY||The key of the Azure Blob Storage for storing the original documents to be processed|
|AZURE_BLOB_ACCOUNT_NAME||The name of the Azure Blob Storage for storing the original documents to be processed|
|AZURE_BLOB_CONTAINER_NAME||The name of the Container in the Azure Blob Storage for storing the original documents to be processed|
|AZURE_CLIENT_ID | | Client ID for Azure authentication (required for LangChain AzureSearch vector store)|
|AZURE_COMPUTER_VISION_ENDPOINT | | The endpoint of the Azure Computer Vision service (if useAdvancedImageProcessing=true)|
|AZURE_COMPUTER_VISION_VECTORIZE_IMAGE_API_VERSION | 2024-02-01 | The API version for Azure Computer Vision Vectorize Image|
|AZURE_COMPUTER_VISION_VECTORIZE_IMAGE_MODEL_VERSION | 2023-04-15 | The model version for Azure Computer Vision Vectorize Image|
|AZURE_CONTENT_SAFETY_ENDPOINT | | The endpoint of the Azure AI Content Safety service|
|AZURE_CONTENT_SAFETY_KEY | | The key of the Azure AI Content Safety service|
|AZURE_COSMOSDB_ACCOUNT_NAME | | The name of the Azure Cosmos DB account (when using CosmosDB)|
|AZURE_COSMOSDB_CONVERSATIONS_CONTAINER_NAME | | The name of the Azure Cosmos DB conversations container (when using CosmosDB)|
|AZURE_COSMOSDB_DATABASE_NAME | | The name of the Azure Cosmos DB database (when using CosmosDB)|
|AZURE_COSMOSDB_ENABLE_FEEDBACK | true | Whether to enable feedback functionality in Cosmos DB|
|AZURE_FORM_RECOGNIZER_ENDPOINT||The name of the Azure Form Recognizer for extracting the text from the documents|
|AZURE_FORM_RECOGNIZER_KEY||The key of the Azure Form Recognizer for extracting the text from the documents|
|AZURE_KEY_VAULT_ENDPOINT | | The endpoint of the Azure Key Vault for storing secrets|
|AZURE_OPENAI_API_KEY||One of the API keys of your Azure OpenAI resource|
|AZURE_OPENAI_API_VERSION|2024-02-01|API version when using Azure OpenAI on your data|
|AZURE_OPENAI_EMBEDDING_MODEL|text-embedding-ada-002|The name of your Azure OpenAI embeddings model deployment|
|AZURE_OPENAI_EMBEDDING_MODEL_NAME|text-embedding-ada-002|The name of the embeddings model (can be found in Azure AI Foundry)|
|AZURE_OPENAI_EMBEDDING_MODEL_VERSION|2|The version of the embeddings model to use (can be found in Azure AI Foundry)|
|AZURE_OPENAI_MAX_TOKENS|1000|The maximum number of tokens allowed for the generated answer.|
|AZURE_OPENAI_MODEL||The name of your model deployment|
|AZURE_OPENAI_MODEL_NAME|gpt-4.1|The name of the model|
|AZURE_OPENAI_MODEL_VERSION|2024-05-13|The version of the model to use|
|AZURE_OPENAI_RESOURCE||the name of your Azure OpenAI resource|
|AZURE_OPENAI_STOP_SEQUENCE||Up to 4 sequences where the API will stop generating further tokens. Represent these as a string joined with "|", e.g. `"stop1|stop2|stop3"`|
|AZURE_OPENAI_STREAM | true | Whether or not to stream responses from Azure OpenAI|
|AZURE_OPENAI_SYSTEM_MESSAGE|You are an AI assistant that helps people find information.|A brief description of the role and tone the model should use|
|AZURE_OPENAI_TEMPERATURE|0|What sampling temperature to use, between 0 and 2. Higher values like 0.8 will make the output more random, while lower values like 0.2 will make it more focused and deterministic. A value of 0 is recommended when using your data.|
|AZURE_OPENAI_TOP_P|1.0|An alternative to sampling with temperature, called nucleus sampling, where the model considers the results of the tokens with top_p probability mass. We recommend setting this to 1.0 when using your data.|
|AZURE_POSTGRESQL_DATABASE_NAME | postgres | The name of the Azure PostgreSQL database (when using PostgreSQL)|
|AZURE_POSTGRESQL_HOST_NAME | | The hostname of the Azure PostgreSQL server (when using PostgreSQL)|
|AZURE_POSTGRESQL_USER | | The username for Azure PostgreSQL authentication (when using PostgreSQL)|
|AZURE_SEARCH_CHUNK_COLUMN | chunk | Field from your Azure AI Search index that contains chunk information|
|AZURE_SEARCH_CONTENT_COLUMN||List of fields in your Azure AI Search index that contains the text content of your documents to use when formulating a bot response. Represent these as a string joined with "|", e.g. `"product_description|product_manual"`|
|AZURE_SEARCH_CONTENT_VECTOR_COLUMN||Field from your Azure AI Search index for storing the content's Vector embeddings|
|AZURE_SEARCH_CONVERSATIONS_LOG_INDEX | conversations | The name of the Azure AI Search conversations log index|
|AZURE_SEARCH_DATASOURCE_NAME | | The name of the Azure AI Search datasource|
|AZURE_SEARCH_DIMENSIONS|1536| Azure OpenAI Embeddings dimensions. 1536 for `text-embedding-ada-002`. A full list of dimensions can be found [here](https://learn.microsoft.com/en-us/azure/ai-services/openai/concepts/models#embeddings-models). |
|AZURE_SEARCH_ENABLE_IN_DOMAIN|True|Limits responses to only queries relating to your data.|
|AZURE_SEARCH_FIELDS_ID|id|`AZURE_SEARCH_FIELDS_ID`: Field from your Azure AI Search index that gives a unique identifier of the document chunk. `id` if you don't have a specific requirement.|
|AZURE_SEARCH_FIELDS_METADATA|metadata|Field from your Azure AI Search index that contains metadata for the document. `metadata` if you don't have a specific requirement.|
|AZURE_SEARCH_FIELDS_TAG|tag|Field from your Azure AI Search index that contains tags for the document. `tag` if you don't have a specific requirement.|
|AZURE_SEARCH_FILENAME_COLUMN||`AZURE_SEARCH_FILENAME_COLUMN`: Field from your Azure AI Search index that gives a unique identifier of the source of your data to display in the UI.|
|AZURE_SEARCH_FILTER||Filter to apply to search queries.|
|AZURE_SEARCH_INDEX||The name of your Azure AI Search Index|
|AZURE_SEARCH_INDEXER_NAME | | The name of the Azure AI Search indexer|
|AZURE_SEARCH_INDEX_IS_PRECHUNKED | false | Whether the search index is prechunked|
|AZURE_SEARCH_KEY||An **admin key** for your Azure AI Search resource|
|AZURE_SEARCH_LAYOUT_TEXT_COLUMN|layoutText|Field from your Azure AI Search index that contains the layout-aware text content of your documents. `layoutText` if you don't have a specific requirement.|
|AZURE_SEARCH_OFFSET_COLUMN | offset | Field from your Azure AI Search index that contains offset information|
|AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG|default|The name of the semantic search configuration to use if using semantic search.|
|AZURE_SEARCH_SERVICE||The URL of your Azure AI Search resource. e.g. https://<search-service>.search.windows.net|
|AZURE_SEARCH_SOURCE_COLUMN|source|Field from your Azure AI Search index that identifies the source of your data. `source` if you don't have a specific requirement.|
|AZURE_SEARCH_TEXT_COLUMN|text|Field from your Azure AI Search index that contains the main text content of your documents. `text` if you don't have a specific requirement.|
|AZURE_SEARCH_TITLE_COLUMN||Field from your Azure AI Search index that gives a relevant title or header for your data content to display in the UI.|
|AZURE_SEARCH_TOP_K|5|The number of documents to retrieve from Azure AI Search.|
|AZURE_SEARCH_URL_COLUMN||Field from your Azure AI Search index that contains a URL for the document, e.g. an Azure Blob Storage URI. This value is not currently used.|
|AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION ||Whether to use [Integrated Vectorization](https://learn.microsoft.com/en-us/azure/search/vector-search-integrated-vectorization). If the database type is PostgreSQL, set this to false.|
|AZURE_SEARCH_USE_SEMANTIC_SEARCH|False|Whether or not to use semantic search|
|AZURE_SPEECH_RECOGNIZER_LANGUAGES | en-US,fr-FR,de-DE,it-IT | Comma-separated list of languages to recognize from speech input|
|AZURE_SPEECH_REGION_ENDPOINT | | The regional endpoint of the Azure Speech service|
|AZURE_SPEECH_SERVICE_KEY | | The key of the Azure Speech service|
|AZURE_SPEECH_SERVICE_NAME | | The name of the Azure Speech service|
|AZURE_SPEECH_SERVICE_REGION | | The region (location) of the Azure Speech service|
|AzureWebJobsStorage__accountName||The name of the Azure Blob Storage account for the Azure Functions Batch processing|
|BACKEND_URL||The URL for the Backend Batch Azure Function. Use http://localhost:7071 for local execution|
|CONVERSATION_FLOW | custom | Chat conversation type: custom or byod (Bring Your Own Data)|
|DATABASE_TYPE | PostgreSQL | The type of database to deploy (cosmos or postgres)|
|DOCUMENT_PROCESSING_QUEUE_NAME|doc-processing|The name of the Azure Queue to handle the Batch processing|
|FUNCTION_KEY | | The function key for accessing the backend Azure Function|
|LOGLEVEL | INFO | The log level for application logging (CRITICAL, ERROR, WARN, INFO, DEBUG)|
|PACKAGE_LOGGING_LEVEL | WARNING | Enhanced: Azure SDK package logging level (CRITICAL, ERROR, WARN, INFO, DEBUG)|
|AZURE_LOGGING_PACKAGES | (optional) | Enhanced: Comma-separated list of Azure logger packages to configure. If not provided, no Azure SDK logging is configured.|
|MANAGED_IDENTITY_CLIENT_ID | | The client ID of the user-assigned managed identity|
|MANAGED_IDENTITY_RESOURCE_ID | | The resource ID of the user-assigned managed identity|
|OPEN_AI_FUNCTIONS_SYSTEM_PROMPT | | System prompt for OpenAI functions orchestration|
|ORCHESTRATION_STRATEGY | openai_function | Orchestration strategy. Use Azure OpenAI Functions (openai_function), Semantic Kernel (semantic_kernel),  LangChain (langchain) or Prompt Flow (prompt_flow) for messages orchestration. If you are using a new model version 0613 select any strategy, if you are using a 0314 model version select "langchain". Note that both `openai_function` and `semantic_kernel` use OpenAI function calling. Prompt Flow option is still in development and does not support RBAC or integrated vectorization as of yet.|
|SEMANTIC_KERNEL_SYSTEM_PROMPT | | System prompt used by the Semantic Kernel orchestration|
|USE_ADVANCED_IMAGE_PROCESSING | false | Whether to enable the use of a vision LLM and Computer Vision for embedding images. If the database type is PostgreSQL, set this to false.|
|USE_KEY_VAULT | true | Whether to use Azure Key Vault for storing secrets|
