# Deployment Guide

## Overview

This guide walks you through deploying the **Chat With Your Data (CWYD) v2 Solution Accelerator** to Azure. The deployment process takes approximately **10–15 minutes** for the default Development/Testing configuration and includes both infrastructure provisioning and application setup.

CWYD v2 is a Foundry-first RAG accelerator built on FastAPI + LangGraph + Microsoft Agent Framework + Foundry IQ. A single `databaseType` parameter selects both the chat-history backend and the vector index store. Two orchestrators (Agent Framework, LangGraph) run on a shared Foundry Project.

> **🆘 Need Help?** If you encounter any issues during deployment, see the [Troubleshooting](#troubleshooting) section at the end of this guide.

> **Note:** Some tenants may have additional security restrictions that run periodically and could impact the application (e.g., blocking public network access). If you experience issues, consider deploying the WAF-aligned version (`avm-waf` deployment flavor) to ensure compliance. See [Step 3.1](#31-choose-deployment-flavor-optional).

---

## Step 1: Prerequisites & Setup

### 1.1 Azure Account Requirements

Ensure you have access to an [Azure subscription](https://azure.microsoft.com/free/) with the following permissions:

| Role | Scope | Purpose |
|------|-------|---------|
| Contributor | Subscription level | Create and manage Azure resources |
| User Access Administrator | Subscription level | Manage user access and role assignments |
| Role Based Access Control Admin | Subscription/Resource Group level | Configure RBAC permissions |

**🔍 How to Check Your Permissions:**

1. Go to [Azure Portal](https://portal.azure.com/)
2. Navigate to **Subscriptions** (search in the top search bar)
3. Click on your target subscription
4. In the left menu, click **Access control (IAM)**
5. Scroll down to see the table with your assigned roles — you should see:
   - Contributor
   - User Access Administrator
   - Role Based Access Control Administrator (or similar RBAC role)

### 1.2 Required Tools

Install the following tools before proceeding:

| Tool | Minimum Version | Installation |
|------|----------------|--------------|
| [Azure Developer CLI (azd)](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd) | `>= 1.18.0` (excluding `1.23.9`) | `winget install microsoft.azd` |
| [Azure CLI (az)](https://learn.microsoft.com/cli/azure/install-azure-cli) | Latest | `winget install Microsoft.AzureCLI` |
| [Python](https://www.python.org/downloads/) | 3.11+ | `winget install Python.Python.3.11` |
| [Node.js](https://nodejs.org/) | 20+ | `winget install OpenJS.NodeJS.LTS` |
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) | Latest | Required for container-based deployments |
| [uv](https://docs.astral.sh/uv/) | Latest | `pip install uv` or `winget install astral-sh.uv` |

### 1.3 Check Service Availability & Quota

> ⚠️ **CRITICAL:** Before proceeding, ensure your chosen regions have the required services available.

**Required Azure Services:**

- [Azure AI Foundry](https://learn.microsoft.com/azure/ai-foundry)
- [Azure OpenAI Service](https://learn.microsoft.com/azure/ai-services/openai/)
- [Azure AI Search](https://learn.microsoft.com/azure/search/search-what-is-azure-search) (Cosmos DB mode only)
- [Azure Container Apps](https://learn.microsoft.com/azure/container-apps/)
- [Azure App Service](https://learn.microsoft.com/azure/app-service/overview)
- [Azure Functions (Flex Consumption)](https://learn.microsoft.com/azure/azure-functions/)
- [Azure Storage](https://learn.microsoft.com/azure/storage/)
- [Azure Cosmos DB](https://learn.microsoft.com/azure/cosmos-db/introduction) or [PostgreSQL Flexible Server](https://learn.microsoft.com/azure/postgresql/flexible-server/)
- [Azure Speech Service](https://learn.microsoft.com/azure/ai-services/speech-service/)
- [Azure Content Safety](https://learn.microsoft.com/azure/ai-services/content-safety/)

**Allowed Primary Regions (infrastructure):**
- Australia East
- East US 2
- Japan East
- UK South

> **Note:** The primary location (`AZURE_LOCATION`) is restricted to these 4 regions to guarantee compatibility with zone-redundant HA, paired-region replicas, and Storage GZRS. The AI Service location (`AZURE_AI_SERVICE_LOCATION`) supports a broader set — see [Step 3.3](#33-advanced-configuration-optional).

**Allowed AI Service Regions:**
Australia East, Canada East, East US 2, Japan East, Korea Central, Poland Central, Sweden Central, Switzerland North, UAE North, UK South, West US 3

**Default Model Deployments:**

| Model | Default | Type | Capacity |
|-------|---------|------|----------|
| GPT (Chat) | `gpt-5.1` | GlobalStandard | 150k TPM |
| Reasoning | `o4-mini` | GlobalStandard | 50k TPM |
| Embedding | `text-embedding-3-large` | Standard | 100k TPM |

**🔍 Check Availability:** Use [Azure Products by Region](https://azure.microsoft.com/en-us/explore/global-infrastructure/products-by-region/) to verify service availability.

---

## Step 2: Choose Your Deployment Environment

Select one of the following options:

### Environment Comparison

| Environment | Best For | Requirements | Setup Time |
|------------|----------|-------------|------------|
| GitHub Codespaces | Quick deployment, no local setup | GitHub account | ~3–5 minutes |
| VS Code Dev Containers | Fast deployment with local tools | Docker Desktop, VS Code | ~5–10 minutes |
| Local Environment | Enterprise environments, full control | All tools individually | ~15–30 minutes |

**💡 Recommendation:** For fastest deployment, start with **GitHub Codespaces** — no local installation required.

### Option A: GitHub Codespaces (Easiest)

1. Navigate to the repository on GitHub
2. Click the **Code** button → **Codespaces** tab → **Create codespace on main**
3. Wait for the codespace to build (includes all tools pre-installed)
4. Proceed to [Step 3](#step-3-configure-deployment-settings)

### Option B: VS Code Dev Containers

1. Install [VS Code](https://code.visualstudio.com/) and the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)
2. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/)
3. Clone the repository and open it in VS Code
4. When prompted, click **Reopen in Container** (or use the Command Palette: `Dev Containers: Reopen in Container`)
5. Proceed to [Step 3](#step-3-configure-deployment-settings)

### Option C: Local Environment

1. Install all tools from [1.2 Required Tools](#12-required-tools)
2. Clone the repository:
   ```bash
   git clone <repository-url>
   cd chat-with-your-data-solution-accelerator/v2
   ```
3. Install Python dependencies:
   ```bash
   uv sync
   ```
4. Proceed to [Step 3](#step-3-configure-deployment-settings)

---

## Step 3: Configure Deployment Settings

Review the configuration options below. You can customize any settings that meet your needs, or leave them as defaults for a standard deployment.

### 3.1 Choose Deployment Flavor (Optional)

| | Default (Vanilla Bicep) | AVM | AVM WAF-Aligned |
|---|---|---|---|
| **Deployment Flavor** | `bicep` | `avm` | `avm-waf` |
| **Configuration File** | `main.parameters.json` (default) | Set `DEPLOYMENT_FLAVOR=avm` | Copy `main.waf.parameters.json` to `main.parameters.json` |
| **Security Controls** | Minimal (for rapid iteration) | Enterprise-grade modules | Enhanced (production best practices) |
| **Monitoring** | Disabled | Disabled | Enabled (Log Analytics + App Insights) |
| **Private Networking** | Disabled | Disabled | Enabled (VNet + Private Endpoints + Bastion) |
| **Scalability** | Disabled | Disabled | Enabled |
| **Redundancy** | Disabled | Disabled | Configurable |
| **Use Case** | POCs, development, testing | Enterprise modules without WAF networking | Production workloads |

> **Note:** An intermediate option (`avm`) is available — it uses Azure Verified Modules without WAF networking features. Set `DEPLOYMENT_FLAVOR` to `avm` for enterprise-grade modules without private endpoints.

**To use the WAF-aligned (production) configuration:**

1. Navigate to the `infra/` folder in your project
2. Open `main.waf.parameters.json`
3. Copy its contents into `main.parameters.json`
4. Save the file

Or set the deployment flavor via environment variable:

```bash
azd env set DEPLOYMENT_FLAVOR avm-waf
```

### 3.2 Choose Database Type

The `databaseType` parameter selects **both** the chat-history backend and the vector index store. This choice is **locked at deploy time** — you cannot switch in-place after provisioning.

| | Cosmos DB Mode | PostgreSQL Mode |
|---|---|---|
| **Parameter Value** | `cosmosdb` | `postgresql` (default) |
| **Chat History** | Azure Cosmos DB (NoSQL) | PostgreSQL Flexible Server |
| **Vector Index** | Azure AI Search | PostgreSQL with pgvector |
| **Additional Resources** | AI Search service + Foundry↔Search connection | pgvector extension (auto-created) |
| **Orchestrator Support** | `langgraph` and `agent_framework` | `langgraph` only |

To set the database type:

```bash
azd env set DATABASE_TYPE cosmosdb
# or
azd env set DATABASE_TYPE postgresql
```

### 3.3 Advanced Configuration (Optional)

**Configurable Parameters:**

You can override any parameter via `azd env set`:

| Parameter | Environment Variable | Default | Description |
|-----------|---------------------|---------|-------------|
| GPT Model | `AZURE_GPT_MODEL_NAME` | `gpt-5.1` | Primary chat model |
| GPT Capacity | `AZURE_GPT_MODEL_CAPACITY` | `150` | Token capacity (thousands TPM) |
| Reasoning Model | `AZURE_REASONING_MODEL_NAME` | `o4-mini` | Reasoning model |
| Embedding Model | `AZURE_EMBEDDING_MODEL_NAME` | `text-embedding-3-large` | Embedding model |
| AI Service Region | `AZURE_AI_SERVICE_LOCATION` | *(prompted)* | Region for AI model deployments |
| Ingestion Trigger | `INGESTION_TRIGGER` | `direct_enqueue` | `direct_enqueue` or `event_grid` |
| Container Registry | `AZURE_CONTAINER_REGISTRY_ENDPOINT` | `testapreg.azurecr.io` | Container image source |
| Image Tag | `AZURE_IMAGE_TAG` | `cwyd` | Container image tag |

**Reuse Existing Resources:**

To reuse existing Azure resources (e.g., for v1→v2 coexistence):

```bash
# Reuse an existing Foundry Project
azd env set AZURE_EXISTING_AIPROJECT_RESOURCE_ID "/subscriptions/.../resourceGroups/.../providers/..."

# Reuse an existing Log Analytics workspace
azd env set AZURE_ENV_LOG_ANALYTICS_WORKSPACE_ID "/subscriptions/.../resourceGroups/.../providers/..."
```

### 3.4 Set VM Credentials (WAF Deployment Only)

> **Note:** This section only applies if you selected the `avm-waf` deployment flavor. VMs are not deployed in the default configuration.

By default, random GUIDs are generated for VM credentials. To set custom credentials:

```bash
azd env set AZURE_ENV_VM_ADMIN_USERNAME <your-username>
azd env set AZURE_ENV_VM_ADMIN_PASSWORD <your-password>
```

---

## Step 4: Deploy the Solution

> **💡 Before You Start:** Ensure you have completed all prerequisites in [Step 1](#step-1-prerequisites--setup) and configured your deployment in [Step 3](#step-3-configure-deployment-settings).

### 4.1 Authenticate with Azure

```bash
azd auth login
```

For specific tenants:

```bash
azd auth login --tenant-id <tenant-id>
```

> **Finding Your Tenant ID:**
> 1. Open the [Azure Portal](https://portal.azure.com/)
> 2. Navigate to **Microsoft Entra ID** from the left-hand menu
> 3. Under the **Overview** section, locate the **Tenant ID** field and copy the value

### 4.2 Start Deployment

If you are running azd version `1.23.9`, first disable preflight:

```bash
azd config set provision.preflight off
```

Then deploy:

```bash
azd up
```

During deployment, you will be prompted for:

1. **Environment name** (e.g., `cwyddev`) — Must be 3–15 characters, alphanumeric only
2. **Azure subscription** selection
3. **AI Service region** — Select a region with available GPT model quota
4. **Primary location** — Select the region where infrastructure resources will be deployed

**Expected Duration:** 10–15 minutes for the default configuration.

> ⚠️ **Deployment Issues:** If you encounter errors or timeouts, try a different region as there may be capacity constraints. See [Troubleshooting](#troubleshooting) for detailed error solutions.

### 4.3 Post-Deployment Setup

After `azd up` completes, the output will display post-deployment instructions. Follow them:

**Windows (PowerShell):**

```powershell
az login
./infra/scripts/post-provision/post_deployment_setup.ps1 -ResourceGroupName "$env:AZURE_RESOURCE_GROUP"
```

**Linux/macOS (Bash):**

```bash
az login
bash ./infra/scripts/post-provision/post_deployment_setup.sh "$AZURE_RESOURCE_GROUP"
```

The post-provision script performs the following idempotent operations:
- **PostgreSQL mode:** Creates the `pgvector` extension if not present
- **Cosmos DB mode:** Ensures the chat index exists with the correct schema
- Validates required environment variables, database connectivity, and Azure token access

**Exit Codes:**

| Code | Meaning |
|------|---------|
| 0 | Success |
| 2 | Missing required environment variable |
| 3 | Missing pip dependencies |
| 4 | Azure token acquisition failure |
| 5 | Database connection failure |
| 6 | Invalid `AZURE_DB_TYPE` |
| 7 | Private-mode DNS unreachable (pre-flight warning) |

### 4.4 Get Application URLs

After successful deployment, retrieve your application URLs:

```bash
azd env get-values | grep -E "AZURE_BACKEND_URL|AZURE_FRONTEND_URL|AZURE_FUNCTION_APP_URL"
```

Or find them in the [Azure Portal](https://portal.azure.com/):

1. Navigate to your resource group
2. Locate the following resources:

| Resource Type | Naming Pattern | Purpose |
|--------------|---------------|---------|
| Container App | `ca-backend-<suffix>` | Backend API (FastAPI) |
| App Service | `app-frontend-<suffix>` | Frontend (React/Vite SPA) |
| Function App | `func-<suffix>` | Indexing pipeline (Azure Functions) |

---

## Step 5: Verify Deployment

### 5.1 Health Check

Verify the backend is running:

```bash
curl https://<your-backend-url>/api/health
```

Expected response: a JSON object with service health status.

### 5.2 Smoke Verification Matrix

Verify the following end-to-end:

| # | Check | How |
|---|-------|-----|
| 1 | Backend liveness | `GET /api/health` returns `200` |
| 2 | OpenAPI schema | `GET /docs` loads Swagger UI |
| 3 | Frontend loads | Navigate to frontend URL in browser |
| 4 | Chat round-trip | Send a message and receive a grounded response |
| 5 | Citations present | Response includes document citations |
| 6 | SSE streaming | Chat response streams via Server-Sent Events |
| 7 | Document upload | Upload a document via the admin interface |
| 8 | Indexing pipeline | Uploaded document gets indexed (check Function App logs) |
| 9 | Chat history | Conversation history persists across page reloads |

### 5.3 Test the Application

1. Sign in to the application using the frontend URL
2. Navigate to the chat interface and test with sample questions:
   - Ask questions about uploaded documents
   - Test different query types (factual, analytical, summary)
   - Verify citations are rendered correctly
3. Verify core functionality:
   - ✅ Document upload and indexing
   - ✅ Grounded chat responses with citations
   - ✅ SSE streaming
   - ✅ Chat history persistence
   - ✅ Speech input/output (if Speech Service is configured)

---

## Step 6: Clean Up (Optional)

### Remove All Resources

```bash
azd down
```

The `azd down` command removes all resources in the resource group and optionally purges them to free up quota.

> **Note:** If you deployed with `enableRedundancy=true` and Log Analytics workspace replication is enabled, you must first disable replication before running `azd down`, otherwise the resource group deletion will fail.

### Manual Cleanup (if needed)

If deployment fails or you need to clean up manually:

1. Go to [Azure Portal](https://portal.azure.com/)
2. Navigate to **Resource groups**
3. Find and select the resource group created by the deployment
4. Click **Delete resource group**
5. Confirm by typing the resource group name

---

## Managing Multiple Environments

### Recover from Failed Deployment

If your deployment failed or encountered errors:

1. Check the error messages in the terminal output
2. Fix the underlying issue (quota, permissions, region availability)
3. Re-run `azd up` — the deployment is idempotent and will resume where it left off

### Creating a New Environment

```bash
# Create a new environment
azd env new <environment-name>

# Configure the new environment
azd env set AZURE_LOCATION <region>
azd env set DATABASE_TYPE <cosmosdb|postgresql>

# Deploy
azd up
```

### Switch Between Environments

```bash
# List environments
azd env list

# Select an environment
azd env select <environment-name>
```

### Best Practices for Multiple Environments

- Use descriptive names: `cwyddev`, `cwydprod`, `cwydtest` (3–15 chars, alphanumeric only)
- Deploy to different regions to test quota availability
- Each environment can have different parameter settings
- Clean up unused environments with `azd down`

---

## Deploying Individual Services

After the initial `azd up`, you can redeploy individual services without re-provisioning infrastructure:

```bash
# Deploy backend only
azd deploy backend

# Deploy frontend only
azd deploy frontend

# Deploy functions only
azd deploy function
```

---

## Local Development

For local development and debugging, see [Local Development Guide](local_development.md).

**Quick Start:**

```bash
# Full v2 stack (backend + frontend + functions + dependencies)
docker compose -f docker/docker-compose.dev.yml up

# Backend-only profile
docker compose -f docker/docker-compose.dev.yml --profile backend-only up

# Frontend-only profile (set VITE_BACKEND_URL to point at a running backend)
docker compose -f docker/docker-compose.dev.yml --profile frontend-only up
```

**What runs where (local dev):**

| Service | Port | Technology |
|---------|------|-----------|
| Backend | `:8000` | FastAPI (uvicorn with hot-reload) |
| Functions | `:7071` | Azure Functions host |
| Frontend | `:5273` | Vite dev server with HMR |
| PostgreSQL | `:5432` | Local PostgreSQL container |
| Azurite | `:10000–10002` | Azure Storage emulator |

> **Identity:** Local dev uses `AzureCliCredential` (your `az login` session). Set `AZURE_UAMI_CLIENT_ID` to empty for local dev. See [Environment Variables](env-vars.md) for full configuration details.

---

## Azure Resource Topology

### Always-On Resources (all deployments)

| Resource | Purpose |
|----------|---------|
| User-Assigned Managed Identity | Workload identity for all v2 services |
| AI Services Account | Foundry substrate for chat/embedding models |
| Foundry Project | Agent Framework + Foundry IQ knowledge bases |
| Storage Account | Documents, config, deployment packages + queues |
| Container Apps Environment + Backend | FastAPI backend on workload-profile consumption |
| App Service Plan + Frontend Web App | React/Vite SPA served by Python + uvicorn |
| Function App (Flex Consumption) | Modular RAG indexing pipeline |
| Event Grid System Topic | BlobCreated/BlobDeleted → Storage queue |
| Speech Service (S0) | Browser-based STT/TTS |
| Content Safety Service (S0) | Prompt shielding guard |

### Database-Conditional Resources

**Cosmos DB mode (`cosmosdb`):**
- Cosmos DB NoSQL account (chat history)
- Azure AI Search service (vector index + Foundry IQ integration)
- Foundry Project ↔ Search connection

**PostgreSQL mode (`postgresql`):**
- PostgreSQL Flexible Server (15+) with pgvector extension
- No Azure AI Search deployment

### WAF-Conditional Resources (`avm-waf` flavor)

**Monitoring (`enableMonitoring=true`):**
- Log Analytics workspace
- Application Insights
- Diagnostic settings on all applicable resources

**Private Networking (`enablePrivateNetworking=true`):**
- VNet (10.0.0.0/20) with 5–6 subnets
- Private DNS zones (6 always-on + 1–2 database-specific)
- Private endpoints for AI Services, Storage, Cosmos/Search, PostgreSQL
- Azure Bastion (Standard SKU) for operator access
- Container Apps Environment internal networking

---

## Troubleshooting

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| `azd up` fails with quota error | Insufficient model capacity in selected region | Try a different AI Service region or reduce model capacity |
| `azd up` fails with permission error | Missing required Azure roles | Verify roles per [1.1 Azure Account Requirements](#11-azure-account-requirements) |
| Post-provision script fails (exit 5) | Database connection failure | Check that the database is accessible and credentials are correct |
| Post-provision script fails (exit 7) | Private DNS unreachable | Expected in private networking mode — connect via Bastion |
| Frontend returns 502 | Backend not ready | Wait for Container App to finish starting; check backend health endpoint |
| Docker build fails | BuildKit not enabled | Ensure Docker Desktop is updated and BuildKit is enabled |
| Functions not triggering | Event Grid subscription missing | Verify `ingestionTrigger` parameter and Function App deployment |
| ACR pull errors | Container registry authentication | Verify `AZURE_CONTAINER_REGISTRY_ENDPOINT` and image permissions |

### Useful Commands

```bash
# View all environment values
azd env get-values

# Check deployment status
az deployment group list --resource-group <rg-name> --output table

# View backend logs (Container Apps)
az containerapp logs show --name <ca-name> --resource-group <rg-name>

# View function app logs
az functionapp log tail --name <func-name> --resource-group <rg-name>

# Re-provision infrastructure only (no code deploy)
azd provision

# Re-deploy code only (no infrastructure changes)
azd deploy
```

---

## Next Steps

Now that your deployment is complete and tested, explore these resources:

**📚 Learn More:**
- [Infrastructure Guide](infrastructure.md) — Understand the system design and Bicep architecture
- [Environment Variables](env-vars.md) — Complete reference for all configuration variables
- [Architecture Decision Records](adr/) — Understand key design decisions
- [Development Plan](development_plan.md) — Roadmap and phase planning

**🔧 Development:**
- [Local Development Guide](local_development.md) — Set up your local dev environment
- [Extending the Solution](extending.md) — Add custom plugins and providers
- [Architecture Pillars](pillars_of_development.md) — Core engineering principles

---

## Need Help?

- 🐛 **Issues:** Check the [Troubleshooting](#troubleshooting) section above
- 📖 **Environment Variables:** See [env-vars.md](env-vars.md)
- 🏗️ **Infrastructure:** See [infrastructure.md](infrastructure.md)
- 🔧 **Local Development:** See [local_development.md](local_development.md)
