# Guide: Migrating Azure Web App Service to a New Container Registry

## Overview

### Current Problem:
- The **CWYD Container Image** is being published in the **GBB ACR** (Azure Container Registry).

### Goal:
- The goal is to **migrate container images** from various applications to a common **CSA CTO Production Azure Container Registry**, ensuring all the different images are consolidated in one centralized location.

---

## Step-by-Step Guide: Migrating Azure Web App Service to a New Container Registry

This guide will help you seamlessly switch the container registry for your **Azure Web App Service** from Azure Container Registry (ACR) to the new registry **`cwydcontainerreg`**.

Follow the steps below to ensure a smooth migration.

### Prerequisites:
Before you begin, ensure you have the following:
- Access to the **Azure Portal**.
- **Credentials** for the new container registry (**`cwydcontainerreg`**).
- **Permissions** to update the Azure Web App Service settings.
- The **container image** in the new registry is ready and accessible.

---

### Step 1: Obtain Details for the New Registry

Before you begin, ensure you have the following information:
- **Registry URL**: The URL of the new registry (`cwydcontainerreg.azurecr.io`).
- **Image Name and Tag**: The full name and tag of the image you want to use:
  - **Web App Image**: `cwydcontainerreg.azurecr.io/rag-webapp:latest`
  - **Admin Web App Image**: `cwydcontainerreg.azurecr.io/rag-adminwebapp:latest`
  - **Function App Image**: `cwydcontainerreg.azurecr.io/rag-backend:latest`

---

### Step 2: Update Azure Web App Service Configuration Using Azure Portal

1. **Log in to Azure Portal**:
   - Open [Azure Portal](https://portal.azure.com/).

2. **Locate Your Web App Service**:
   - In the search bar, type your **Web App Service name** and select it from the list.

3. **Go to the Deployment Center**:
   - In the left-hand menu, click on **Deployment**.

  ![Resource Menu](images/resource_menu.png)


4. **Update Image Source**:
   - Change the **Registry Source** to **Private**.
   - Set the **Server URL** to the new container registry (`cwydcontainerreg`), as shown in the screenshot below.
   - Set the **Full Image name** to the relevant image name and tag:
     - For Web App: `cwydcontainerreg.azurecr.io/webapp:latest`
     - For Admin Web App: `cwydcontainerreg.azurecr.io/admin-webapp:latest`
     - For Function App: `cwydcontainerreg.azurecr.io/rag-backend:latest`
   - Leave **Tag** as it is, or if needed, specify a tag ( `latest` or specific version tags).


   ![Deployment Center](images/deployment_center.png)


5. **Save Changes**:
   - Click **Save** to save the configuration.

---

### Step 3: Update Azure Admin Web App Service Configuration Using Azure Portal

1. **Locate Your Admin Web App Service**:
   - In the search bar, type your **Admin Web App Service name** and select it from the list.

2. **Go to the Deployment Center**:
   - In the left-hand menu, click on **Deployment**.

3. **Update Image Source for Admin Web App**:
   - Change the **Registry Source** to **Private**.
   - Set the **Server URL** to the new container registry (`cwydcontainerreg`).
   - Set the **Full Image name** to the relevant image name and tag:
     - For **Admin Web App**: `cwydcontainerreg.azurecr.io/admin-webapp:latest`
   - Leave **Tag** as it is, or specify a tag if needed (e.g., `latest`, or a version tag like `v1.0.0`).

4. **Save Changes**:
   - Click **Save** to save the configuration.

---

### Step 4: Update Azure Function App Service Configuration Using Azure Portal

1. **Locate Your Function Web App Service**:
   - In the search bar, type your **Function Web App Service name** and select it from the list.

2. **Go to the Deployment Center**:
   - In the left-hand menu, click on **Deployment**.

3. **Update Image Source for Function App**:
   - Change the **Registry Source** to **Private**.
   - Set the **Server URL** to the new container registry (`cwydcontainerreg`).
   - Set the **Full Image name** to the relevant image name and tag:
     - For **Function App**: `cwydcontainerreg.azurecr.io/rag-backend:latest`
   - Leave **Tag** as it is, or specify a tag if needed (e.g., `latest`, or a version tag like `v1.0.0`).

4. **Save Changes**:
   - Click **Save** to save the configuration.

---

### Step 3: Restart the Web App Service

After updating the configuration, restart your **Web App Service** to apply the changes:

1. In the **Web App Service overview page**, click on **Restart**.
2. Confirm the restart operation.

---

### Step 4: Update Azure Admin Web App Service Configuration

1. **Locate Your Admin Web App Service**:
   - In the search bar, type your **Admin Web App Service name** and select it from the list.

2. **Repeat Steps 2.3 to 2.5**:
   - Repeat the steps mentioned in **Step 2** for your **Admin Web App** and follow the same process.

---

### Step 5: Restart the Admin Web App Service

After updating the configuration, restart your **Admin Web App Service** to apply the changes:

1. In the **Admin Web App Service overview page**, click on **Restart**.
2. Confirm the restart operation.

---

### Step 6: Validate the Deployment

1. **Access Your Web App**:
   - Open the **Web App URL** in a browser to ensure it’s running correctly.

2. **Access Your Admin Web App**:
   - Open the **Admin Web App URL** in a browser to ensure it’s running correctly.

---

By following these steps, your **Azure Web App Service** will now use the new container from the **CWYD registry**.

For further assistance, feel free to reach out to your support team or log an issue on GitHub.

---
