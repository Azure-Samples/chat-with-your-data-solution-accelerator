# Migrating Azure Web App Service to a New Container Registry

This guide will help you seamlessly switch the container registry for your Azure Web App Service from Azure Container Registry (ACR) to the new registry, `csactoprod`. Follow the steps below to ensure a smooth migration.

## Current Problem

The CWYD Container Image is currently being published in the GBB ACR (Azure Container Registry).

We have a similar issue with Doc Gen, although it’s less severe since the Container Image is published in the James Hunter ACR.

## Goal

The goal is to migrate container images from various applications to a common CSA CTO Production Azure Container Registry, ensuring all the different images are consolidated in one centralized location.

## Prerequisites

- Access to the Azure Portal.
- Credentials for the new container registry (`csactoprod`).
- Permissions to update the Azure Web App Service settings.
- The container image in the new registry is ready and accessible.

---

## Step 1: Obtain Details for the New Registry

Before you begin, ensure you have the following information:

- **Registry URL**: The URL of the new registry (e.g., `csactoprod.example.com`).
- **Image Name and Tag**: The full name and tag of the image you want to use (e.g., `csactoprod.example.com/myapp:latest`).

---

## Step 2: Update Azure Web App Service Configuration using Azure Portal

### 1. Log in to Azure Portal
Navigate to the Azure Portal.

### 2. Locate Your Web App Service
In the search bar, type your Web App Service name and select it from the list.

### 3. Go to the Deployment Center
In the left-hand menu, click on **Deployment**.

![Menu](image-1.png)

### 4. Update Image Source
Change the **Registry Source** to **Private**, and set the **Server URL** to the new container registry (`csactoprod`).

- Leave **Full Image Name** and **Tag** as is (e.g., `csactoprod.example.com/myapp:latest`).


![Deployment Center](image.png)


### 5. Save Changes
Click on **Save** to save the configuration.

---

## Step 3: Restart the Web App Service

After updating the configuration, restart your Web App Service to apply the changes.

### Using Azure Portal

- In the Web App Service overview page, click on **Restart**.
- Confirm the restart operation.

---

## Step 4: Update Azure Admin Web App Service Configuration using Azure Portal

### 1. Locate Your Admin Web App Service
In the search bar, type your Admin Web App Service name and select it from the list.

### 2. Repeat the Configuration Update
Repeat steps 2.3 to 2.5 for the Admin Web App, ensuring the image source points to the new registry (`csactoprod`).

---

## Step 5: Restart the Admin Web App Service

After updating the configuration, restart your Admin Web App Service to apply the changes.

### Using Azure Portal

- In the Web App Service overview page, click on **Restart**.
- Confirm the restart operation.

---

## Step 6: Validate the Deployment

### 1. Access Your Web App
Open the Web App URL in a browser to ensure it’s running correctly.

### 2. Access Your Admin Web App
Open the Admin Web App URL in a browser to ensure it’s running correctly.

---

By following these steps, your Azure Web App Service will now use the new container from the CWYD registry. For further assistance, feel free to reach out to your support team or log an Issue in GitHub.
