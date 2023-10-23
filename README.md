# Chat with your data Solution Accelerator

[**OVERVIEW**](#overview) | [**GETTING STARTED**](#getting-started) | [**DEPLOY**](#deploy) | [**HOW TO USE**](#how-to-use) | [**TROUBLESHOOTING**](#troubleshooting) | [**MORE INFO**](#more-info) | [**DISCLAIMERS**](#disclaimers)

![Overview](/images/readme/overview.png)
## Overview

The Chat with your data Solution Accelerator allows users to chat with their own unstructured data by combining Azure Cognitive Search and Large Language Models (LLMs) to create a conversational search experience. Users can drag and drop files, point to storage, and take care of technical setup to transform documents. There is a web app that users can create in their own subscription with security and authentication. 

### Key features 
- **Private LLM access on your data**: Get all the benefits of ChatGPT on your private, unstructured data.
- **Single application access to your full data set**: Minimize endpoints required to access internal company knowledgebases  
- **Natural language interaction with your unstructured data**: Use natural language to quickly find the answers you need and ask follow-up queries to get the supplemental details.
- **Easy access to source documentation when querying**: Review referenced documents in the same chat window for additional context.
- **Data upload**: Batch upload documents
- **Accessible orchestration**: Prompt and document configuration (prompt engineering, document processing, and data retrieval)

**Note**: The current model allows users to ask questions about unstructured data, such as PDF, text, and docx files.

### Target end users
Company personnel (employees, executives) looking to research against internal unstructured company data would leverage this accelerator using natural language to find what they need quickly. 

This accelerator also works across industry and roles and would be suitable for any employee who would like to get quick answers with a ChatGPT experience against their internal unstructured company data. 

Tech administrators can use this accelerator to give their colleagues easy access to internal unstructured company data. Admins can customize the system configurator to tailor responses for the intended audience. 

### Industry scenario
The sample data illustrates how this accelerator could be used in the financial services industry (FSI).

In this scenario, a financial advisor is preparing for a meeting with a potential client who has expressed interest in Woodgrove Investments’ Emerging Markets Funds. The advisor prepares for the meeting by refreshing their understanding of the emerging markets fund's overall goals and the associated risks. 

Now that the financial advisor is more informed about Woodgrove’s Emerging Markets Funds, they're better equipped to respond to questions about this fund from their client.  

Note: Some of the sample data included with this accelerator was generated using AI and is for illustrative purposes only.

### Teams extension
By bringing the Chat with your data experience into Teams, users can stay within their current workflow and get the answers they need without switching platforms.  
Rather than building the Chat with your data accelerator within Teams from scratch, the same underlying backend used for the web application is leveraged within Teams. 

![Teams - Chat with your Data](/images/readme/image-27.png)

### Speech-to-text feature
Many users are used to the convenience of speech-to-text functionality in their consumer products. With hybrid work increasing, speech-to-text supports a more flexible way for users to chat with their data, whether they’re at their computer or on the go with their mobile device. 
The speech-to-text capability is combined with NLP capabilities to extract intent and context from spoken language, allowing the chatbot to understand and respond to user requests more intelligently.

![Web - Chat with unstructured data](/images/readme/web-unstructureddata.png)Chat with your unstructured data

![Web - Get responses using natural language](/images/readme/web-nlu.png)Get responses using natural language

![Getting started](/images/readme/gettingstarted.png)
## Getting started

### Pre-requisites 
- Azure subscription - [Create one for free](https://azure.microsoft.com/free/) with contributor access.
- [Visual Studio Code](https://code.visualstudio.com/)
    - Extensions
        - [Azure Functions](https://marketplace.visualstudio.com/items?itemName=ms-azuretools.vscode-azurefunctions)
        - [Azure Tools](https://marketplace.visualstudio.com/items?itemName=ms-vscode.vscode-node-azure-pack)
        - [Bicep](https://marketplace.visualstudio.com/items?itemName=ms-azuretools.vscode-bicep)
        - [Docker](https://marketplace.visualstudio.com/items?itemName=ms-azuretools.vscode-docker)
        - [Pylance](https://marketplace.visualstudio.com/items?itemName=ms-python.vscode-pylance)
        - [Python](https://marketplace.visualstudio.com/items?itemName=ms-python.python)
        - [Teams Toolkit](https://marketplace.visualstudio.com/items?itemName=TeamsDevApp.ms-teams-vscode-extension)
- Install [Node.js](https://nodejs.org/en)
  - Install the LTS version (Recommended for Most Users)
- [Enable custom Teams apps and turn on custom app uploading](https://learn.microsoft.com/en-us/microsoftteams/platform/concepts/build-and-test/prepare-your-o365-tenant#enable-custom-teams-apps-and-turn-on-custom-app-uploading)

### Products used
- Azure App Service
- Azure Application Insights
- Azure Bot
- Azure OpenAI
- Azure Document Intelligence
- Azure Function App
- Azure Search Service
- Azure Storage Account
- Azure Speech Service
- Teams

### Required licenses
- No required licenses

![Deploy](/images/readme/deploy.png)
## Deploy

### Speech-to-text deployment
Click [here for more details on local debugging and deployment](/web/README.md).
#### Supported file types

Out-of-the-box, you can upload the following file types:
* PDF
* JPEG
* JPG
* PNG
* TXT
* HTML
* MD (Markdown)
* DOCX

#### Prerequisites

* Azure subscription - [Create one for free](https://azure.microsoft.com/free/) with contributor access.
* An [Azure OpenAI resource](https://learn.microsoft.com/azure/ai-services/openai/how-to/create-resource?pivots=web-portal) and a deployment for one of the following Chat model and an embedding model:
    * Chat Models
       * GPT-3.5
       * GPT-4
  * Embedding Model 
     * text-embedding-ada-002
    
  **NOTE**: The deployment template defaults to **gpt-35-turbo** and **text-embedding-ada-002**. If your deployment names are different, update them in the deployment process.

#### Steps

1. Click the following deployment button to create the required resources for this accelerator directly in your Azure Subscription. 

    [![Deploy to Azure](https://aka.ms/deploytoazurebutton)](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2FAzure-Samples%2Fchat-with-your-data-solution-accelerator%2Fmain%2Fweb%2Finfrastructure%2Fdeployment.json)
1. Add the following fields:

    
    |Field  |Description  |
    |---------|---------|
    |Resource group   | The resource group that will contain the resources for this accelerator. You can select **Create new** to create a new group.        |
    |Resource prefix   | A text string that will be appended to each resource that gets created, and used as the website name for the web app. This name cannot contain spaces or special characters.        |
    |Azure OpenAI resource    | The name of your Azure OpenAI resource. This resource must have already been created previously.         |
    |Azure OpenAI key    | The access key is associated with your Azure OpenAI resource.        |
    |Orchestration strategy| Use Azure OpenAI Functions (openai_functions) or LangChain (langchain) for messages orchestration. If you are using a new model version 0613 select "openai_functions" (or "langchain"), if you are using model version 0314 select "langchain"|
   
    
    You can find the [ARM template](/web/infrastructure/deployment.json) used, along with a [Bicep file](/web/infrastructure/deployment.bicep) for deploying this accelerator in the `web/infrastructure` directory.

   **NOTE**: By default, the deployment name in the application settings is equal to the model’s name (gpt-35-turbo and text-embedding-ada-002). If you named the deployment in a different way, you should update the application settings to match your deployment names.

#### Accelerator architecture for speech-to-text feature
![Solution Architecture - Speech-to-text](/images/readme/solutionarchitecture-speechtotext.png)

### Teams deployment
**IMPORTANT**: Before you proceed, installation and configuration of the [Speech-to-text deployment](#speech-to-text-deployment) is required.
#### Deploy Backend Azure Function
[![Deploy to Azure](https://aka.ms/deploytoazurebutton)](https://portal.azure.com/#create/Microsoft.Template/uri/https://raw.githubusercontent.com/Azure-Samples/chat-with-your-data-solution-accelerator/main/extensions/infrastructure/deployment.json)

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

#### Deploy Teams App 
1. Clone this GitHub repo.
1. Open the “extensions/teams” folder with Visual Studio Code 
![Teams](/images/readme/image.png) 
1. Open the file env\.env.test
![ENV](/images/readme/image-1.png) 
1. Locate the environment variable AZURE_FUNCTION_URL.
1. Replace the <YOUR AZURE FUNCTION NAME> with the name of your Function App resource (created in previous section)
1. Save the file.
1. Select Teams Toolkit from the navigation panel. 
![Teams Toolkit in VS Code](/images/readme/image-2.png) 
1. Within the Teams Toolkit panel, login to the following accounts:
  **Sign in to Microsoft 365**: Use your Microsoft 365 work or school account with a valid E5 subscription for building your app. If you don't have a valid account, you can join [Microsoft 365 developer program](https://developer.microsoft.com/microsoft-365/dev-program) to get a free account before you start.
  **Sign in to Azure**: Use your Azure account for deploying your app on Azure. You can [create a free Azure account](https://azure.microsoft.com/free/) before you start.
![Teams Toolkit Accounts](/images/readme/image-3.png)
1. Under **Environment**, select **test**.
![Teams Toolkit Environment](/images/readme/image-4.png)
1. Under **Lifecycle**, select **Provision**.
![Teams Toolkit Lifecycle Provision](/images/readme/image-5.png)
1. Within the command palette, select **test** for the environment.
![Select an Environment](/images/readme/image-6.png) 
1. Select the resource group created earlier in the installation
![Select a Resource Group](/images/readme/image-7.png) 
1. When prompted about Azure charges, select **Provision**.
![Azure Charges Prompt](/images/readme/image-8.png)
1. Verify that the provisioning was successful.
![Provision Successful](/images/readme/image-9.png)
1. Under **Lifecycle**, select **Deploy**.
![Teams Toolkit Lifecycle Deploy](/images/readme/image-10.png) 
1. Within the command palette, select **test** for the environment.
![Select an Environment](/images/readme/image-6.png) 
1. When prompted, select **Deploy**.
![VS Code Prompt to Deploy](/images/readme/image-11.png) 
1. Verify that the Deployment was successful.
![Deployment successful](/images/readme/image-12.png)
1. Under **Lifecycle**, select **Publish**.
![Teams Toolkit Lifecycle Publish](/images/readme/image-13.png)
1. Within the command palette, select **test** for the environment.
![Select an Environment](/images/readme/image-6.png) 
1. Verify that the Publish was successful.
![Publishing successful](/images/readme/image-14.png) 
1. Select **Go to admin portal**.
![Go to Admin Portal](/images/readme/image-15.png) 
1. On the Manage apps page within the Teams Admin portal, you should see one submitted custom app pending approval.
![Pending Approval](/images/readme/image-16.png) 
1. In the search by name input box, enter: **enterprise chat**
![Filtered app](/images/readme/image-17.png) 
1. Select the app and then select **Allow**.
![Selected app](/images/readme/image-18.png) 
1. Select the app name.
![Select app name](/images/readme/image-19.png) 
1. Select **Publish**.
![Publish app](/images/readme/image-20.png)
1. When prompted, select **Publish**.
![Prompt to publish](/images/readme/image-21.png) 
1. Depending on your environment, it may take several hours to publish.
![Teams Publish Success](/images/readme/image-22.png) 

#### Accelerator architecture for Teams integration
![Solution Architecture - Teams](/images/readme/solutionarchitecture-teams.png)

![How to use](/images/readme/howtouse.png)
## How to use

### Web application with speech-to-text feature
1. Navigate to the admin site, where you can upload documents. It will be located at:
https://{MY_RESOURCE_PREFIX}-website-admin.azurewebsites.net/
Where {MY_RESOURCE_PREFIX} is replaced with the resource prefix you used during deployment. Then select Ingest Data and add your data. You can find sample data in the /data directory.
![Admin Portal - Ingest Data](/images/readme/image-29.png)
1. Navigate to the web app to start chatting on top of your data. The web app can be found at:
https://{MY_RESOURCE_PREFIX}-website.azurewebsites.net/
Where {MY_RESOURCE_PREFIX} is replaced with the resource prefix you used during deployment.
1. Select microphone to enable speech-to-text. Depress the microphone to disable speech-to-text.
![Web Portal - Speech to Text](/images/readme/image-30.png)

### Teams extension
1. Open [Teams](https://teams.microsoft.com/)
1. Select **Apps->Built for your org->Add**
![Add app to Teams](/images/readme/image-31.png)
1. Select **Add**.
![Select the Add button in Teams](/images/readme/image-32.png)
1. Type a question and select the **Send** icon.
![Chat with your Data Teams Interface](/images/readme/image-33.png)

![Troubleshooting](/images/readme/troubleshooting.png)
## Troubleshooting

### Response consistency 

#### Persistent chat vs session-based chat
Responses may vary between the web application and Teams due to persistent vs session-based chat.
With the web app, context from the prior questions is included in responses. For example, when you ask a follow up question after your first question, the context from the previous questions impacts the response of follow up questions. To clear the previous context, simply clear the chat with the sweep button to the left of the chat window.
For Teams, context from previous chats do not impact follow up questions. This is because each question is self-contained without context from prior questions. In Teams, that chat is persistent. It is currently not possible for the LLM to determine if the prior question relates to the current question.

#### ChatGPT3.5 vs ChatGPT4
If you’re using ChatGPT 3.5 Turbo and experiencing many inconsistencies in your responses, we recommend switching to ChatGPT 4. 

#### Configuration tuning
Consider tuning the configuration of prompts to the level of precision required. The more precision desired, the harder it may be to generate a response.  

### Teams deployment
Upon publishing an app within the Teams store (within the Teams admin portal), it is common to see an extended availability delay within the “Apps” section of Teams. In addition, once the app does display within the “Apps” section of Teams, a “Something went wrong" upon selecting “Add”. Reason being the app is still in the process of deploying.

### Reference documentation in Teams
When an AI response is provided within Teams, the reference article(s) points to an Azure Blob container. Users may not have access to this container, resulting in an error. Due to the limitations of the Teams interface via Bot, rendering a citation panel (like the web-based interface) is outside the scope of this accelerator.

### Speech Service delay
There is a speech delay between a user's spoken words and the recognition and display of those words. This delay can occur for various reasons and can impact the user experience during real-time speech recognition applications. It can be attributed to some of these factors:
- **Network Latency**: In cloud-based speech recognition, the time it takes for audio data to travel to the server and for the recognized text to return can introduce delay.
- **Server Processing**: The server-side processing of audio data, including transcription and natural language processing, can take some time.

![More info](/images/readme/moreinfo.png)
## More info

### Best practices
**Access to documents**

Only upload data that can be accessed by any user of the application. Anyone who uses the application should also have clearance for any data that is uploaded to the application.

**Depth of responses**

The more limited the data set, the broader the questions should be. If the data in the repo is limited, the depth of information in the LLM response you can get with follow up questions may be limited. For more depth in your response, increase the data available for the LLM to access.  

**Response consistency**

Consider tuning the configuration of prompts to the level of precision required.  The more precision desired, the harder it may be to generate a response.

**Numerical queries**

The accelerator is optimized to summarize unstructured data, such as PDFs or text files. The ChatGPT 3.5 Turbo model used by the accelerator is not currently optimized to handle queries about specific numerical data. The ChatGPT 4 model may be better able to handle numerical queries.  

**Use your own judgement**

AI-generated content may be incorrect and should be reviewed before usage.

### Resource links for *Chat with your data* Solution Accelerator
- [Application Insights overview - Azure Monitor | Microsoft Learn](https://learn.microsoft.com/en-us/azure/azure-monitor/app/app-insights-overview?tabs=net)
- [Azure OpenAI Service - Documentation, quickstarts, API reference - Azure AI services | Microsoft Learn](https://learn.microsoft.com/en-us/azure/ai-services/openai/concepts/use-your-data)
- [Using your data with Azure OpenAI Service - Azure OpenAI | Microsoft Learn](https://learn.microsoft.com/en-us/azure/ai-services/openai/concepts/use-your-data)
- [Content Safety documentation - Quickstarts, Tutorials, API Reference - Azure AI services | Microsoft Learn](https://learn.microsoft.com/en-us/azure/ai-services/content-safety/)
- [Document Intelligence documentation - Quickstarts, Tutorials, API Reference - Azure AI services | Microsoft Learn](https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/?view=doc-intel-3.1.0)
- [Azure Functions documentation | Microsoft Learn](https://learn.microsoft.com/en-us/azure/azure-functions/)
- [Azure Cognitive Search documentation | Microsoft Learn](https://learn.microsoft.com/en-us/azure/search/)

### Resource links for speech-to-text feature
- [Speech to text documentation - Tutorials, API Reference - Azure AI services - Azure AI services | Microsoft Learn](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/index-speech-to-text)

### Resource links for Teams extension
- [Bots in Microsoft Teams - Teams | Microsoft Learn](https://learn.microsoft.com/en-us/microsoftteams/platform/bots/what-are-bots)

![Disclaimers](/images/readme/disclaimers.png)
## Disclaimers 

This Software requires the use of third-party components which are governed by separate proprietary or open-source licenses as identified below, and you must comply with the terms of each applicable license in order to use the Software. You acknowledge and agree that this license does not grant you a license or other right to use any such third-party proprietary or open-source components.  

To the extent that the Software includes components or code used in or derived from Microsoft products or services, including without limitation Microsoft Azure Services (collectively, “Microsoft Products and Services”), you must also comply with the Product Terms applicable to such Microsoft Products and Services. You acknowledge and agree that the license governing the Software does not grant you a license or other right to use Microsoft Products and Services. Nothing in the license or this ReadMe file will serve to supersede, amend, terminate or modify any terms in the Product Terms for any Microsoft Products and Services. 

You must also comply with all domestic and international export laws and regulations that apply to the Software, which include restrictions on destinations, end users, and end use. For further information on export restrictions, visit https://aka.ms/exporting. 

You acknowledge that the Software and Microsoft Products and Services (1) are not designed, intended or made available as a medical device(s), and (2) are not designed or intended to be a substitute for professional medical advice, diagnosis, treatment, or judgment and should not be used to replace or as a substitute for professional medical advice, diagnosis, treatment, or judgment. Customer is solely responsible for displaying and/or obtaining appropriate consents, warnings, disclaimers, and acknowledgements to end users of Customer’s implementation of the Online Services. 

You acknowledge the Software is not subject to SOC 1 and SOC 2 compliance audits. No Microsoft technology, nor any of its component technologies, including the Software, is intended or made available as a substitute for the professional advice, opinion, or judgement of a certified financial services professional. Do not use the Software to replace, substitute, or provide professional financial advice or judgment.  

BY ACCESSING OR USING THE SOFTWARE, YOU ACKNOWLEDGE THAT THE SOFTWARE IS NOT DESIGNED OR INTENDED TO SUPPORT ANY USE IN WHICH A SERVICE INTERRUPTION, DEFECT, ERROR, OR OTHER FAILURE OF THE SOFTWARE COULD RESULT IN THE DEATH OR SERIOUS BODILY INJURY OF ANY PERSON OR IN PHYSICAL OR ENVIRONMENTAL DAMAGE (COLLECTIVELY, “HIGH-RISK USE”), AND THAT YOU WILL ENSURE THAT, IN THE EVENT OF ANY INTERRUPTION, DEFECT, ERROR, OR OTHER FAILURE OF THE SOFTWARE, THE SAFETY OF PEOPLE, PROPERTY, AND THE ENVIRONMENT ARE NOT REDUCED BELOW A LEVEL THAT IS REASONABLY, APPROPRIATE, AND LEGAL, WHETHER IN GENERAL OR IN A SPECIFIC INDUSTRY. BY ACCESSING THE SOFTWARE, YOU FURTHER ACKNOWLEDGE THAT YOUR HIGH-RISK USE OF THE SOFTWARE IS AT YOUR OWN RISK.  

