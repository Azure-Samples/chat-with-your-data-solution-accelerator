# Local Deployment Guide

## Overview

This guide walks you through deploying the Chat with your Data solution accelerator to Azure from you local environment. The deployment process takes approximately 40-50 minutes for the default Development/Testing configuration and includes both infrastructure provisioning and application setup.

<!-- 🆘 **Need Help?** If you encounter any issues during setup, check our [Troubleshooting Guide](./TroubleShootingSteps.md) for solutions to common problems. -->

## Step 1: Prerequisites & Setup

### 1.1 Azure Account Requirements

Ensure you have access to an [Azure subscription](https://azure.microsoft.com/free/) with the following permissions:

| **Required Permission/Role** | **Scope** | **Purpose** |
|------------------------------|-----------|-------------|
| **Contributor** | Subscription level | Create and manage Azure resources |
| **User Access Administrator** | Subscription level | Manage user access and role assignments |
| **Role Based Access Control** | Subscription/Resource Group level | Configure RBAC permissions |
| **App Registration Creation** | Azure Active Directory | Create and configure authentication |

**🔍 How to Check Your Permissions:**

1. Go to [Azure Portal](https://portal.azure.com/)
2. Navigate to **Subscriptions** (search for "subscriptions" in the top search bar)
3. Click on your target subscription
4. In the left menu, click **Access control (IAM)**
5. Scroll down to see the table with your assigned roles - you should see:
   - **Contributor**
   - **User Access Administrator**
   - **Role Based Access Control Administrator** (or similar RBAC role)

**For App Registration permissions:**
1. Go to **Microsoft Entra ID** → **Manage** → **App registrations**
2. Try clicking **New registration**
3. If you can access this page, you have the required permissions
4. Cancel without creating an app registration

📖 **Detailed Setup:** Follow [Azure Account Set Up](./azure_account_setup.md) for complete configuration.

### 1.2 Check Service Availability & Quota

⚠️ **CRITICAL:** Before proceeding, ensure your chosen region has all required services available:

**Required Azure Services:**
- [Azure OpenAI Service](https://learn.microsoft.com/en-us/azure/ai-services/openai/)
- [Azure Document Intelligence](https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence)
- [Azure Function App](https://learn.microsoft.com/en-us/azure/azure-functions/)
- [Azure App Service](https://learn.microsoft.com/en-us/azure/app-service/)
- [Azure Search Service](https://learn.microsoft.com/en-us/azure/search/)
- [Azure Blob Storage](https://learn.microsoft.com/en-us/azure/storage/blobs/)
- [Azure PostgreSQL](https://learn.microsoft.com/en-us/azure/postgresql/)
- [Azure Cosmos DB](https://learn.microsoft.com/en-us/azure/cosmos-db/)
- [Azure Queue Storage](https://learn.microsoft.com/en-us/azure/storage/queues/)
- [gpt-4.1, text-embeddings-ada-002 Model Capacity](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-models/concepts/models-sold-directly-by-azure)
- [Azure Bot](https://learn.microsoft.com/en-us/azure/bot-service) (optional: Teams extension only)
- [Teams](https://learn.microsoft.com/en-us/microsoftteams/teams-overview) (optional: Teams extension only)

**Recommended Regions:** East US, East US2, Australia East, UK South, France Central

🔍 **Check Availability:** Use [Azure Products by Region](https://azure.microsoft.com/en-us/explore/global-infrastructure/products-by-region/) to verify service availability.

### 1.3 Quota Check (Optional)

💡 **RECOMMENDED:** Check your Azure OpenAI quota availability before deployment for optimal planning.

📖 **Follow:** [Quota Check Instructions](./QuotaCheck.md) to ensure sufficient capacity.

**Recommended Configuration:**

| **Model** | **Minimum Capacity** | **Recommended Capacity** |
|-----------|---------------------|--------------------------|
| **gpt-4.1** | 150k tokens | 200k tokens (for best performance) |
| **text-embedding-ada-002** | 100k tokens | 150k tokens (for best performance) |

> **Note:** When you run `azd up`, the deployment will automatically show you regions with available quota, so this pre-check is optional but helpful for planning purposes. You can customize these settings later in [Step 3.3: Advanced Configuration](#33-advanced-configuration-optional).

📖 **Adjust Quota:** Follow [Azure AI Model Quota Settings](./azure_openai_model_quota_settings.md) if needed.

## Step 2: Choose Your Development Environment

Select one of the following options to set up your Chat with your Data local deployment environment:

### Environment Comparison

| **Option** | **Best For** | **Prerequisites** | **Setup Time** |
|------------|--------------|-------------------|----------------|
| **VS Code Dev Containers** | Fastest setup, all tools included | Docker Desktop, VS Code | ~5-10 minutes |
| **Local Environment** | Full control, custom setup | All tools individually | ~15-30 minutes |

**💡 Recommendation:** For local development, start with **VS Code Dev Containers** - includes all tools pre-configured.

---

<details>
<summary><b>Option A: VS Code Dev Containers (Recommended)</b></summary>

[![Open in Dev Containers](https://img.shields.io/static/v1?style=for-the-badge&label=Dev%20Containers&message=Open&color=blue&logo=visualstudiocode)](https://vscode.dev/redirect?url=vscode://ms-vscode-remote.remote-containers/cloneInVolume?url=https://github.com/azure-samples/chat-with-your-data-solution-accelerator)

⚠️ **Note for macOS Developers**: If you are using macOS on Apple Silicon (ARM64) the DevContainer will **not** work. This is due to a limitation with the Azure Functions Core Tools (see [here](https://github.com/Azure/azure-functions-core-tools/issues/3112)). We recommend using the [Non DevContainer Setup](./NON_DEVCONTAINER_SETUP.md) instructions to run the accelerator locally.

**Prerequisites:**
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- [VS Code](https://code.visualstudio.com/) with [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)

**Steps:**
1. Start Docker Desktop
2. Click the badge above to open in Dev Containers
3. Wait for the container to build and start (includes all development tools)
4. Proceed to [Step 3: Configure Azure Resources](#step-3-configure-deployment-settings)

**💡 Tip:** Visual Studio Code should recognize the available development container and ask you to open the folder using it. For additional details on connecting to remote containers, please see the [Open an existing folder in a container](https://code.visualstudio.com/docs/remote/containers#_quick-start-open-an-existing-folder-in-a-container) quickstart.

</details>

<details>
<summary><b>Option B: Local Environment</b></summary>

**Required Tools:**
- A code editor. We recommend [Visual Studio Code](https://code.visualstudio.com/), with the following extensions:
  - [Azure Functions](https://marketplace.visualstudio.com/items?itemName=ms-azuretools.vscode-azurefunctions)
  - [Azure Tools](https://marketplace.visualstudio.com/items?itemName=ms-vscode.vscode-node-azure-pack)
  - [Bicep](https://marketplace.visualstudio.com/items?itemName=ms-azuretools.vscode-bicep)
  - [Pylance](https://marketplace.visualstudio.com/items?itemName=ms-python.vscode-pylance)
  - [Python](https://marketplace.visualstudio.com/items?itemName=ms-python.python)
  - [Teams Toolkit](https://marketplace.visualstudio.com/items?itemName=TeamsDevApp.ms-teams-vscode-extension) **Optional**
- [Python 3.11](https://www.python.org/downloads/release/python-3119/)
- [Node.js LTS](https://nodejs.org/en)
- [Azure Developer CLI](https://learn.microsoft.com/en-us/azure/developer/azure-developer-cli/install-azd) <small>(v1.18.0+)</small>
- [Azure Functions Core Tools](https://docs.microsoft.com/en-us/azure/azure-functions/functions-run-local)
- [Git](https://git-scm.com/downloads)
- [PowerShell 7.0+](https://learn.microsoft.com/en-us/powershell/scripting/install/installing-powershell)

**Setup Steps:**
1. Install all required deployment tools listed above
2. Clone the repository:
   ```shell
   azd init -t chat-with-your-data-solution-accelerator
   ```
3. Open the project folder in your terminal
4. Review the contents of [.devcontainer/setupEnv.sh](../.devcontainer/setupEnv.sh) and then run it:

    ```bash
    .devcontainer/setupEnv.sh
    ```
5. Select the Python interpreter in Visual Studio Code:

    - Open the command palette (`Ctrl+Shift+P` or `Cmd+Shift+P`).
    - Type `Python: Select Interpreter`.
    - Select the Python 3.11 environment created by Poetry.
6. Proceed to [Step 3: Configure Azure Resources](#step-3-configure-deployment-settings)

**PowerShell Users:** If you encounter script execution issues, run:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

</details>

## Step 3: Configure Deployment Settings

Review the configuration options below. You can customize any settings that meet your needs, or leave them as defaults to proceed with a standard deployment.

### 3.1 Choose Deployment Type (Optional)

| **Aspect** | **Development/Testing (Default)** | **Production** |
|------------|-----------------------------------|----------------|
| **Configuration File** | `main.parameters.json` (sandbox) | Copy `main.waf.parameters.json` to `main.parameters.json` |
| **Security Controls** | Minimal (for rapid iteration) | Enhanced (production best practices) |
| **Cost** | Lower costs | Cost optimized |
| **Use Case** | POCs, development, testing | Production workloads |
| **Framework** | Basic configuration | [Well-Architected Framework](https://learn.microsoft.com/en-us/azure/well-architected/) |
| **Features** | Core functionality | Reliability, security, operational excellence |

**To use production configuration:**

Copy the contents from the production configuration file to your main parameters file:

1. Navigate to the `infra` folder in your project
2. Open `main.waf.parameters.json` in a text editor (like Notepad, VS Code, etc.)
3. Select all content (Ctrl+A) and copy it (Ctrl+C)
4. Open `main.parameters.json` in the same text editor
5. Select all existing content (Ctrl+A) and paste the copied content (Ctrl+V)
6. Save the file (Ctrl+S)

### 3.2 Set VM Credentials (Optional - Production Deployment Only)

> **Note:** This section only applies if you selected **Production** deployment type in section 3.1. VMs are not deployed in the default Development/Testing configuration.

By default, random GUIDs are generated for VM credentials. To set custom credentials:

```shell
azd env set AZURE_ENV_VM_ADMIN_USERNAME <your-username>
azd env set AZURE_ENV_VM_ADMIN_PASSWORD <your-password>
```

### 3.3 Advanced Configuration (Optional)

<details>
<summary><b>Configurable Parameters</b></summary>

You can customize various deployment settings before running `azd up`, including Azure regions, AI model configurations (deployment type, version, capacity), container registry settings, and resource names.

📖 **Complete Guide:** See [Parameter Customization Guide](./customizing_azd_parameters.md) for the full list of available parameters and their usage.

</details>

<details>
<summary><b>Reuse Existing Resources</b></summary>

To optimize costs and integrate with your existing Azure infrastructure, you can configure the solution to reuse compatible resources already deployed in your subscription.

**Supported Resources for Reuse:**

- **Log Analytics Workspace:** Integrate with your existing monitoring infrastructure by reusing an established Log Analytics workspace for centralized logging and monitoring. [Configuration Guide](./re-use-log-analytics.md)

- **Resource Group:** Leverage an existing resource group to organize resources within your current Azure infrastructure. Follow the [setup steps here](./re-use-resource-group.md) before running `azd up`

**Key Benefits:**
- **Cost Optimization:** Eliminate duplicate resource charges
- **Operational Consistency:** Maintain unified monitoring and AI infrastructure
- **Faster Deployment:** Skip resource creation for existing compatible services
- **Simplified Management:** Reduce the number of resources to manage and monitor

**Important Considerations:**
- Ensure existing resources meet the solution's requirements and are in compatible regions
- Review access permissions and configurations before reusing resources
- Consider the impact on existing workloads when sharing resources

</details>

## Step 4: Deploy the Solution

<!-- 💡 **Before You Start:** If you encounter any issues during deployment, check our [Troubleshooting Guide](./TroubleShootingSteps.md) for common solutions. -->

### 4.1 Authenticate with Azure

```shell
azd auth login
```

**For specific tenants:**
```shell
azd auth login --tenant-id <tenant-id>
```

> **Finding Tenant ID:**
   > 1. Open the [Azure Portal](https://portal.azure.com/).
   > 2. Navigate to **Microsoft Entra ID** from the left-hand menu.
   > 3. Under the **Overview** section, locate the **Tenant ID** field. Copy the value displayed.

### 4.2 Start Deployment

```shell
azd up
```

**During deployment, you'll be prompted for:**
1. **Environment name** (e.g., "cwyd") - Must be 3-16 characters long, alphanumeric only
2. **Azure subscription** selection
3. **Location** - Select the region where your infrastructure resources will be deployed
5. **Resource group** selection (create new or use existing)

**Expected Duration:** 25-30 minutes for default configuration

<!-- **⚠️ Deployment Issues:** If you encounter errors or timeouts, try a different region as there may be capacity constraints. For detailed error solutions, see our [Troubleshooting Guide](./TroubleShootingSteps.md). -->

### 4.3 Get Application URL

After successful deployment, locate your application URLs:

1. Open the [Azure Portal](https://portal.azure.com/)
2. Navigate to your resource group
3. Locate the **App Services** - you'll find two deployments:
   - **Chat Application:** App Service without "admin" suffix - Main chat interface
   - **Admin Application:** App Service with "admin" suffix - Data management interface
4. Click on each App Service and copy its **Default Domain** URL from the overview page

**Example URLs:**
- Chat App: `https://app-<unique-text>.azurewebsites.net`
- Admin App: `https://app-<unique-text>-admin.azurewebsites.net`

⚠️ **Important:** Complete [Post-Deployment Steps](#step-5-post-deployment-configuration) before accessing the application.

## Step 5: Post-Deployment Configuration

### 5.1 Configure Authentication (Required for Chat Application)

**This step is mandatory for Chat Application access:**

1. Follow [App Authentication Configuration](./azure_app_service_auth_setup.md)
2. Wait up to 10 minutes for authentication changes to take effect

### 5.2 Verify Deployment

1. Access your application using the URL from Step 4.3
2. Confirm the application loads successfully
3. Verify you can sign in with your authenticated account

### 5.3 Test the Application

**Quick Test Steps:**
1. Navigate to the admin site, where you can upload documents. Then select Ingest Data and add your data. You can find sample data in the [data](../data) directory.
2. Navigate to the Chat web app to start chatting on top of your data.

## Step 6: Clean Up (Optional)

### Remove All Resources
```shell
azd down
```
> **Note:** If you deployed with `enableRedundancy=true` and Log Analytics workspace replication is enabled, you must first disable replication before running `azd down` else resource group delete will fail. Follow the steps in [Handling Log Analytics Workspace Deletion with Replication Enabled](./LogAnalyticsReplicationDisable.md), wait until replication returns `false`, then run `azd down`.

### Manual Cleanup (if needed)
If deployment fails or you need to clean up manually:
- Follow [Delete Resource Group Guide](./delete_resource_group.md)

## Managing Multiple Environments

### Recover from Failed Deployment

If your deployment failed or encountered errors, here are the steps to recover:

<details>
<summary><b>Recover from Failed Deployment</b></summary>

**If your deployment failed or encountered errors:**

1. **Try a different region:** Create a new environment and select a different Azure region during deployment
2. **Clean up and retry:** Use `azd down` to remove failed resources, then `azd up` to redeploy
3. **Fresh start:** Create a completely new environment with a different name

**Example Recovery Workflow:**
```shell
# Remove failed deployment (optional)
azd down

# Create new environment (3-16 chars, alphanumeric only)
azd env new cwydretry

# Deploy with different settings/region
azd up
```

</details>

### Creating a New Environment

If you need to deploy to a different region, test different configurations, or create additional environments:

<details>
<summary><b>Create a New Environment</b></summary>

**Create Environment Explicitly:**
```shell
# Create a new named environment (3-16 characters, alphanumeric only)
azd env new <new-environment-name>

# Select the new environment
azd env select <new-environment-name>

# Deploy to the new environment
azd up
```

**Example:**
```shell
# Create a new environment for production (valid: 3-16 chars)
azd env new cwydprod

# Switch to the new environment
azd env select cwydprod

# Deploy with fresh settings
azd up
```

> **Environment Name Requirements:**
> - **Length:** 3-16 characters
> - **Characters:** Alphanumeric only (letters and numbers)
> - **Valid examples:** `cwyd`, `test123`, `myappdev`, `prod2024`
> - **Invalid examples:** `cd` (too short), `my-very-long-environment-name` (too long), `test_env` (underscore not allowed), `myapp-dev` (hyphen not allowed)

</details>

<details>
<summary><b>Switch Between Environments</b></summary>

**List Available Environments:**
```shell
azd env list
```

**Switch to Different Environment:**
```shell
azd env select <environment-name>
```

**View Current Environment Variables:**
```shell
azd env get-values
```

</details>

### Best Practices for Multiple Environments

- **Use descriptive names:** `cwyddev`, `cwydprod`, `cwydtest` (remember: 3-16 chars, alphanumeric only)
- **Different regions:** Deploy to multiple regions for testing quota availability
- **Separate configurations:** Each environment can have different parameter settings
- **Clean up unused environments:** Use `azd down` to remove environments you no longer need

## Deploy Using Bicep Directly

If you prefer not to use `azd`, you can deploy using the Bicep file directly.

A [Bicep file](../infra/main.bicep) is used to generate the [ARM template](../infra/main.json). You can deploy this accelerator with the following command:

```sh
az deployment sub create --template-file ./infra/main.bicep --subscription {your_azure_subscription_id} --location {your_preferred_location}
```

## Next Steps

Now that your deployment is complete and tested, explore these resources to enhance your experience:

📚 **Learn More:**
- [Model Configuration](./model_configuration.md) - Configure AI models and parameters
- [Conversation Flow Options](./conversation_flow_options.md) - Customize conversation flow behavior
- [Best Practices](./best_practices.md) - Best practices for deployment and usage
- [Local Development Setup](./LocalDevelopmentSetup.md) - Set up your local development environment
- [Advanced Image Processing](./advanced_image_processing.md) - Enable and configure vision capabilities
- [Integrated Vectorization](./integrated_vectorization.md) - Understanding integrated vectorization
- [Teams Extension](./teams_extension.md) - Integrating with Microsoft Teams

## Need Help?
- 🛠️  **Troubleshooting: ** Refer to the [TroubleShootingSteps](TroubleShootingSteps.md) document
- 💬 **Support:** Review [Support Guidelines](../SUPPORT.md)
- 🔧 **Development:** See [Contributing Guide](../CONTRIBUTING.md)

---

[Back to *Chat with your data* README](../README.md)
