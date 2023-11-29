[Back to *Chat with your data* README](README.md)

# Teams extension
[**USER STORY**](#user-story) | [**ONE-CLICK DEPLOY**](#one-click-deploy) | [**SUPPORTING DOCUMENTATION**](#supporting-documentation)

![User Story](/media/userStory.png)
## User story
This extension brings the Chat with your data experience into Teams, allowing users can stay within their existing workflow and get the answers they need without switching platforms. Rather than building the Chat with your data solution accelerator within Teams from scratch, the same underlying backend used for the web application is leveraged within Teams.

![One-click Deploy](/media/oneClickDeploy.png)
## One-click deploy
**IMPORTANT**: Before you proceed, installation and configuration of the [Chat with your data with speech-to-text deployment](#chat-with-your-data-with-speech-to-text-deployment) is required.
### Deploy Backend Azure Function
<!-- TODO: Updated prior to PR -->
[![Deploy to Azure](https://aka.ms/deploytoazurebutton)](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2Fhunterjam%2Fchat-with-your-data-solution-accelerator%2Fmain%2Fextensions%2Finfrastructure%2Fmain.json)

| App Setting | Note |
| --- | ------------- |
|Resource group | The resource group that will contain the resources for this accelerator. You can select Create new to create a new group or use the existing resource group created with [Speech-to-text deployment](#speech-to-text-deployment). |
|Resource prefix | A text string that will be appended to each resource that gets created, and used as the website name for the web app. This name cannot contain spaces or special characters. |
|App Insights Connection String (p) | The Application Insights connection string to store the application logs. |
|Azure Cognitive Search (p) | The **name** of your Azure Cognitive Search resource. e.g. https://<**name**>.search.windows.net. |
|Azure Search Index (p) | The name of your Azure Cognitive Search Index. |
|Azure Search Key (p) | An admin key for your Azure Cognitive Search resource. |
|Azure OpenAI resource (p) | The name of your Azure OpenAI resource. This resource must have already been created previously. |
|Azure OpenAI key (p) | The access key is associated with your Azure OpenAI resource. |
|Orchestration strategy (p) | Use Azure OpenAI Functions (openai_functions) or LangChain (langchain) for messages orchestration. If you are using a new model version 0613 select "openai_functions" (or "langchain"), if you are using a model version 0314 select "langchain". |
|Azure Form Recognizer Endpoint (p) | The name of the Azure Form Recognizer for extracting the text from the documents. |
|Azure Form Recognizer Key (p) | The key of the Azure Form Recognizer for extracting the text from the documents. |
|Azure Blob Account Name (p) | The name of the Azure Blob Storage for storing the original documents to be processed. |
|Azure Blob Account Key (p) | The key of the Azure Blob Storage for storing the original documents to be processed. |
|Azure Blob Container Name (p) | The name of the Container in the Azure Blob Storage for storing the original documents to be processed. |

You can find the [ARM template](/extensions/infrastructure/main.json) used, along with a [Bicep file](/extensions/infrastructure/main.bicep) for deploying this accelerator in the /infrastructure directory.

### Deploy Teams App 
1. Clone this GitHub repo.
1. Open the “extensions/teams” folder with Visual Studio Code 
![Teams](/media/teams.png) 
1. Open the file env\.env.test
![ENV](/media/teams-1.png) 
1. Locate the environment variable AZURE_FUNCTION_URL.
1. Replace the <YOUR AZURE FUNCTION NAME> with the name of your Function App resource (created in previous section)
1. Save the file.
1. Select Teams Toolkit from the navigation panel. 
![Teams Toolkit in VS Code](/media/teams-2.png) 
1. Within the Teams Toolkit panel, login to the following accounts:
  **Sign in to Microsoft 365**: Use your Microsoft 365 work or school account with a valid E5 subscription for building your app. If you don't have a valid account, you can join [Microsoft 365 developer program](https://developer.microsoft.com/microsoft-365/dev-program) to get a free account before you start.
  **Sign in to Azure**: Use your Azure account for deploying your app on Azure. You can [create a free Azure account](https://azure.microsoft.com/free/) before you start.
![Teams Toolkit Accounts](/media/teams-3.png)
1. Under **Environment**, select **test**.
![Teams Toolkit Environment](/media/teams-4.png)
1. Under **Lifecycle**, select **Provision**.
![Teams Toolkit Lifecycle Provision](/media/teams-5.png)
1. Within the command palette, select **test** for the environment.
![Select an Environment](/media/teams-6.png) 
1. Select the resource group created earlier in the installation
![Select a Resource Group](/media/teams-7.png) 
1. When prompted about Azure charges, select **Provision**.
![Azure Charges Prompt](/media/teams-8.png)
1. Verify that the provisioning was successful.
![Provision Successful](/media/teams-9.png)
1. Under **Lifecycle**, select **Deploy**.
![Teams Toolkit Lifecycle Deploy](/media/teams-10.png) 
1. Within the command palette, select **test** for the environment.
![Select an Environment](/media/teams-6.png) 
1. When prompted, select **Deploy**.
![VS Code Prompt to Deploy](/media/teams-11.png) 
1. Verify that the Deployment was successful.
![Deployment successful](/media/teams-12.png)
1. Under **Lifecycle**, select **Publish**.
![Teams Toolkit Lifecycle Publish](/media/teams-13.png)
1. Within the command palette, select **test** for the environment.
![Select an Environment](/media/teams-6.png) 
1. Verify that the Publish was successful.
![Publishing successful](/media/teams-14.png) 
1. Select **Go to admin portal**.
![Go to Admin Portal](/media/teams-15.png) 
1. On the Manage apps page within the Teams Admin portal, you should see one submitted custom app pending approval.
![Pending Approval](/media/teams-16.png) 
1. In the search by name input box, enter: **enterprise chat**
![Filtered app](/media/teams-17.png) 
1. Select the app and then select **Allow**.
![Selected app](/media/teams-18.png) 
1. Select the app name.
![Select app name](/media/teams-19.png) 
1. Select **Publish**.
![Publish app](/media/teams-20.png)
1. When prompted, select **Publish**.
![Prompt to publish](/media/teams-21.png) 
1. Depending on your environment, it may take several hours to publish.
![Teams Publish Success](/media/teams-22.png) 

![Supporting documentation](/media/supportingDocuments.png)
## Supporting documentation
### Resource links for Teams extension
This solution accelerator deploys the following resources. It's crucial to comprehend the functionality of each. Below are the links to their respective documentation:
- [Bots in Microsoft Teams - Teams | Microsoft Learn](https://learn.microsoft.com/en-us/microsoftteams/platform/bots/what-are-bots)
