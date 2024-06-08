[Back to *Chat with your data* README](../README.md)

# Local setup

> **Note for macOS Developers**: If you are using macOS on Apple Silicon (ARM64) the DevContainer will **not** work. This is due to a limitation with the Azure Functions Core Tools (see [here](https://github.com/Azure/azure-functions-core-tools/issues/3112)). We recommend using the [Non DevContainer Setup](./NON_DEVCONTAINER_SETUP.md) instructions to run the accelerator locally.

The easiest way to run this accelerator is in a VS Code Dev Containers, which will open the project in your local VS Code using the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers):

1. Start Docker Desktop (install it if not already installed)
1. Open the project:
    [![Open in Dev Containers](https://img.shields.io/static/v1?style=for-the-badge&label=Dev%20Containers&message=Open&color=blue&logo=visualstudiocode)](https://vscode.dev/redirect?url=vscode://ms-vscode-remote.remote-containers/cloneInVolume?url=https://github.com/azure-samples/chat-with-your-data-solution-accelerator)
1. In the VS Code window that opens, once the project files show up (this may take several minutes), open a terminal window
1. Run `azd auth login`
1. Run `azd env set AZURE_APP_SERVICE_HOSTING_MODEL code` - This sets your environment to deploy code rather than rely on public containers, like the "Deploy to Azure" button.
1. Run `azd up` - This will provision Azure resources and deploy the accelerator to those resources.

    * **Important**: Beware that the resources created by this command will incur immediate costs, primarily from the AI Search resource. These resources may accrue costs even if you interrupt the command before it is fully executed. You can run `azd down` or delete the resources manually to avoid unnecessary spending.
    * You will be prompted to select a subscription, and a location. That location list is based on the [OpenAI model availability table](https://learn.microsoft.com/azure/cognitive-services/openai/concepts/models#model-summary-table-and-region-availability) and may become outdated as availability changes.
    * If you do, accidentally, chose the wrong location; you will have to ensure that you use `azd down` or delete the Resource Group as the deployment bases the location from this Resource Group.
1. After the application has been successfully deployed you will see a URL printed to the console.  Click that URL to interact with the application in your browser.

> NOTE: It may take up to an hour for the application to be fully deployed. If you see a "Python Developer" welcome screen or an error page, then wait a bit and refresh the page.

> NOTE: The default auth type uses keys that are stored in the Azure Keyvault. If you want to use RBAC-based auth (more secure), please run before deploying:

```bash
azd env set AZURE_AUTH_TYPE rbac
azd env set USE_KEY_VAULT false
```

Also please refer to the section on [setting up RBAC auth](#authenticate-using-rbac).

## Detailed Development Container setup instructions

The solution contains a [development container](https://code.visualstudio.com/docs/remote/containers) with all the required tooling to develop and deploy the accelerator. To deploy the Chat With Your Data accelerator using the provided development container you will also need:

* [Visual Studio Code](https://code.visualstudio.com)
* [Remote containers extension for Visual Studio Code](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)

If you are running this on Windows, we recommend you clone this repository in [WSL](https://code.visualstudio.com/docs/remote/wsl)

```cmd
git clone https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator
```

Open the cloned repository in Visual Studio Code and connect to the development container.

```cmd
code .
```

!!! tip
    Visual Studio Code should recognize the available development container and ask you to open the folder using it. For additional details on connecting to remote containers, please see the [Open an existing folder in a container](https://code.visualstudio.com/docs/remote/containers#_quick-start-open-an-existing-folder-in-a-container) quickstart.

When you start the development container for the first time, the container will be built. This usually takes a few minutes. **Please use the development container for all further steps.**

The files for the dev container are located in `/.devcontainer/` folder.

## Local debugging

To customize the accelerator or run it locally, you must provision the Azure resources by running `azd provision` in a Terminal. This will generate a `.env` for you and you can use the "Run and Debug" (Ctrl + Shift + D) command to chose which part of the accelerator to run.  There is an [environment variable values table](#environment-variables) below.


To run the accelerator in local when the solution is secured by RBAC you need to assign some roles to your principal id. You can do it either manually or programatically.

### Manually assign roles
You need to assign the following roles to your `PRINCIPALID` (you can get your 'principal id' from Microsoft Entra ID):

| Role | GUID |
|----|----|
|  Cognitive Services OpenAI Contributor | a001fd3d-188f-4b5d-821b-7da978bf7442 |
| Search Service Contributor | 7ca78c08-252a-4471-8644-bb5ff32d4ba0 |
| Search Index Data Contributor | 8ebe5a00-799e-43f5-93ac-243d3dce84a7 |
| Storage Blob Data Reader | 2a2b9908-6ea1-4ae2-8e65-a410df84e7d1 |
| Reader | acdd72a7-3385-48ef-bd42-f606fba81ae7 |

### Programatically assign roles
You can also update the `principalId` value with your own principalId in the `main.bicep` file.

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

The `AzureWebJobsStorage` needs to be added to your `.env` file manually. This can be retrieved from the function
settings via the Azure Portal.

To start the services, you can use either of the following commands:
- `make docker-compose-up`
- `cd docker && AZD_ENV_FILE=<path-to-env-file> docker-compose up`

**Note:** By default, these commands will run the latest Docker images built from the main branch. If you wish to use a
different image, you will need to modify the `docker/docker-compose.yml` file accordingly.

### Develop & run the frontend locally

For faster development, you can run the frontend Typescript React UI app and the Python Flask api app in development mode. This allows the app to "hot reload" meaning your changes will automatically be reflected in the app without having to refresh or restart the local servers.

They can be launched locally from vscode (Ctrl+Shift+D) and selecting "Launch Frontend (api)" and "Launch Frontend (UI). You will also be able to place breakpoints in the code should you wish. This will automatically install any dependencies for Node and Python.


#### Starting the Flask app in dev mode from the command line (optional)
This step is included if you cannot use the Launch configuration in VSCode. Open a terminal and enter the following commands
```shell
cd code
poetry run flask run
```

#### Starting the Typescript React app in dev mode (optional)
This step is included if you cannot use the Launch configuration in VSCode. Open a new separate terminal and enter the following commands:
```shell
cd code\frontend
npm install
npm run dev
```
The local vite server will return a url that you can use to access the chat interface locally, such as  `http://localhost:5174/`.

### Develop & run the admin app

The admin app can be launched locally from vscode (Ctrl+Shift+D) and selecting "Launch Admin site". You will also be able to place breakpoints in the Python Code should you wish.

This should automatically open `http://localhost:8501/` and render the admin interface.

### Develop & run the batch processing functions

If you want to develop and run the batch processing functions container locally, use the following commands.

#### Running the batch processing locally

First, install [Azure Functions Core Tools](https://learn.microsoft.com/en-us/azure/azure-functions/functions-run-local?tabs=windows%2Cportal%2Cv2%2Cbash&pivots=programming-language-python).

```shell
cd code\backend\batch
poetry run func start
```

Or use the [Azure Functions VS Code extension](https://marketplace.visualstudio.com/items?itemName=ms-azuretools.vscode-azurefunctions).

#### Debugging the batch processing functions locally
Rename the file `local.settings.json.sample` in the `batch` folder to `local.settings.json` and update the `AzureWebJobsStorage` value with the storage account connection string.

Copy the .env file from [previous section](#local-debugging) to the `batch` folder.

Execute the above [shell command](#L81) to run the function locally. You may need to stop the deployed function on the portal so that all requests are debugged locally. To trigger the function, you can click on the corresponding URL that will be printed to the terminal.

## Environment variables

| App Setting | Value | Note |
| --- | --- | ------------- |
|AZURE_SEARCH_SERVICE||The URL of your Azure AI Search resource. e.g. https://<search-service>.search.windows.net|
|AZURE_SEARCH_INDEX||The name of your Azure AI Search Index|
|AZURE_SEARCH_KEY||An **admin key** for your Azure AI Search resource|
|AZURE_SEARCH_USE_SEMANTIC_SEARCH|False|Whether or not to use semantic search|
|AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG|default|The name of the semantic search configuration to use if using semantic search.|
|AZURE_SEARCH_TOP_K|5|The number of documents to retrieve from Azure AI Search.|
|AZURE_SEARCH_ENABLE_IN_DOMAIN|True|Limits responses to only queries relating to your data.|
|AZURE_SEARCH_CONTENT_COLUMNS||List of fields in your Azure AI Search index that contains the text content of your documents to use when formulating a bot response. Represent these as a string joined with "|", e.g. `"product_description|product_manual"`|
|AZURE_SEARCH_CONTENT_VECTOR_COLUMNS||Field from your Azure AI Search index for storing the content's Vector embeddings|
|AZURE_SEARCH_DIMENSIONS|1536| Azure OpenAI Embeddings dimensions. 1536 for `text-embedding-ada-002`. A full list of dimensions can be found [here](https://learn.microsoft.com/en-us/azure/ai-services/openai/concepts/models#embeddings-models). |
|AZURE_SEARCH_FIELDS_ID|id|`AZURE_SEARCH_FIELDS_ID`: Field from your Azure AI Search index that gives a unique idenitfier of the document chunk. `id` if you don't have a specific requirement.|
|AZURE_SEARCH_FILENAME_COLUMN||`AZURE_SEARCH_FILENAME_COLUMN`: Field from your Azure AI Search index that gives a unique idenitfier of the source of your data to display in the UI.|
|AZURE_SEARCH_TITLE_COLUMN||Field from your Azure AI Search index that gives a relevant title or header for your data content to display in the UI.|
|AZURE_SEARCH_URL_COLUMN||Field from your Azure AI Search index that contains a URL for the document, e.g. an Azure Blob Storage URI. This value is not currently used.|
|AZURE_SEARCH_FIELDS_TAG|tag|Field from your Azure AI Search index that contains tags for the document. `tag` if you don't have a specific requirement.|
|AZURE_SEARCH_FIELDS_METADATA|metadata|Field from your Azure AI Search index that contains metadata for the document. `metadata` if you don't have a specific requirement.|
|AZURE_SEARCH_FILTER||Filter to apply to search queries.|
|AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION ||Whether to use [Integrated Vectorization](https://learn.microsoft.com/en-us/azure/search/vector-search-integrated-vectorization)|
|AZURE_OPENAI_RESOURCE||the name of your Azure OpenAI resource|
|AZURE_OPENAI_MODEL||The name of your model deployment|
|AZURE_OPENAI_MODEL_NAME|gpt-35-turbo|The name of the model|
|AZURE_OPENAI_API_KEY||One of the API keys of your Azure OpenAI resource|
|AZURE_OPENAI_EMBEDDING_MODEL|text-embedding-ada-002|The name of you Azure OpenAI embeddings model deployment|
|AZURE_OPENAI_TEMPERATURE|0|What sampling temperature to use, between 0 and 2. Higher values like 0.8 will make the output more random, while lower values like 0.2 will make it more focused and deterministic. A value of 0 is recommended when using your data.|
|AZURE_OPENAI_TOP_P|1.0|An alternative to sampling with temperature, called nucleus sampling, where the model considers the results of the tokens with top_p probability mass. We recommend setting this to 1.0 when using your data.|
|AZURE_OPENAI_MAX_TOKENS|1000|The maximum number of tokens allowed for the generated answer.|
|AZURE_OPENAI_STOP_SEQUENCE||Up to 4 sequences where the API will stop generating further tokens. Represent these as a string joined with "|", e.g. `"stop1|stop2|stop3"`|
|AZURE_OPENAI_SYSTEM_MESSAGE|You are an AI assistant that helps people find information.|A brief description of the role and tone the model should use|
|AZURE_OPENAI_API_VERSION|2024-02-01|API version when using Azure OpenAI on your data|
|AzureWebJobsStorage||The connection string to the Azure Blob Storage for the Azure Functions Batch processing|
|BACKEND_URL||The URL for the Backend Batch Azure Function. Use http://localhost:7071 for local execution|
|DOCUMENT_PROCESSING_QUEUE_NAME|doc-processing|The name of the Azure Queue to handle the Batch processing|
|AZURE_BLOB_ACCOUNT_NAME||The name of the Azure Blob Storage for storing the original documents to be processed|
|AZURE_BLOB_ACCOUNT_KEY||The key of the Azure Blob Storage for storing the original documents to be processed|
|AZURE_BLOB_CONTAINER_NAME||The name of the Container in the Azure Blob Storage for storing the original documents to be processed|
|AZURE_FORM_RECOGNIZER_ENDPOINT||The name of the Azure Form Recognizer for extracting the text from the documents|
|AZURE_FORM_RECOGNIZER_KEY||The key of the Azure Form Recognizer for extracting the text from the documents|
|APPLICATIONINSIGHTS_CONNECTION_STRING||The Application Insights connection string to store the application logs|
|ORCHESTRATION_STRATEGY | openai_function | Orchestration strategy. Use Azure OpenAI Functions (openai_function), Semantic Kernel (semantic_kernel),  LangChain (langchain) or Prompt Flow (prompt_flow) for messages orchestration. If you are using a new model version 0613 select any strategy, if you are using a 0314 model version select "langchain". Note that both `openai_function` and `semantic_kernel` use OpenAI function calling. Prompt Flow option is still in development and does not support RBAC or integrated vectorization as of yet.|
|AZURE_CONTENT_SAFETY_ENDPOINT | | The endpoint of the Azure AI Content Safety service |
|AZURE_CONTENT_SAFETY_KEY | | The key of the Azure AI Content Safety service|
|AZURE_SPEECH_SERVICE_KEY | | The key of the Azure Speech service|
|AZURE_SPEECH_SERVICE_REGION | | The region (location) of the Azure Speech service|
|AZURE_AUTH_TYPE | keys | The default is to use API keys. Change the value to 'rbac' to authenticate using Role Based Access Control. For more information refer to section [Authenticate using RBAC](#authenticate-using-rbac)

## Bicep

A [Bicep file](./infra/main.bicep) is used to generate the [ARM template](./infra/main.json). You can deploy this accelerator by the following command if you do not want to use `azd`.

```sh
az deployment sub create --template-file ./infra/main.bicep --subscription {your_azure_subscription_id} --location {search_location}
 ```
