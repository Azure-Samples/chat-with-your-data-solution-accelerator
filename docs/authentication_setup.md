---
title: Set up authentication
description: Sign users in to Chat with Your Data with Microsoft Entra ID through Azure Container Apps built-in authentication, and control who can reach the admin area.
ms.date: 2026-07-03
ms.topic: how-to
---

[Back to *Chat with your data* README](../README.md)

![Supporting documentation](images/supportingDocuments.png)

## Overview

Chat with Your Data signs users in with Microsoft Entra ID through the built-in authentication of Azure Container Apps (Easy Auth). Sign-in is enforced at the platform, before a request reaches the app, so the application never handles passwords or tokens of its own. The workload authenticates to Azure with a managed identity, so there are no application secrets to store or rotate. See [Managed identity and RBAC](managed_identity.md) for that side of the identity model.

When authentication is enabled, three things follow:

- Users must sign in before they can open the web app.
- Each signed-in user sees only their own chat history, because the app reads the caller's identity from the platform and partitions history on it.
- You choose which users can reach the admin area, where documents and application settings are managed.

Sign-in is optional for local development. With no identity provider configured, the app runs as a single shared default user and every feature still works.

## Prerequisites

- Access to Microsoft Entra ID, with permission to create and manage app registrations.
- A deployed environment. Follow [Deploy with azd](LOCAL_DEPLOYMENT.md) first, and note the web app's public URL (its fully qualified domain name).

## Step 1: Register an application in Microsoft Entra ID

An app registration represents Chat with Your Data to Microsoft Entra ID. The built-in authentication uses it to sign users in.

1. In the Azure portal, go to **Microsoft Entra ID** > **App registrations** > **New registration**.
2. Enter a name for the application.
3. Under **Supported account types**, select **Accounts in this organizational directory only (single tenant)**.
4. Under **Redirect URI**, select the **Web** platform and enter the sign-in callback for your deployment: `https://<CONTAINER_APP_FQDN>/.auth/login/aad/callback`.
5. Select **Register**.

To add or change the redirect URI later, open the app registration, go to **Authentication** > **Add a platform** > **Web**, enter the same callback URL, and select **Save**.

Note the **Application (client) ID** and **Directory (tenant) ID** from the overview page. You need them in the next step. Treat these as environment-specific values and keep them out of source control.

## Step 2: Turn on authentication for the web app

1. In the Azure portal, open the web app's Container App and select **Settings** > **Authentication** > **Add identity provider**.
2. Choose **Microsoft** as the identity provider.
3. Select **Pick an existing app registration in this directory** and choose the application you registered in Step 1.
4. Under **Restrict access**, select **Require authentication** so unauthenticated visitors are redirected to sign in.
5. Select **Add**.

Visitors are now prompted to sign in with Microsoft Entra ID before the web app loads.

## Step 3: Choose who can reach the admin area

Any signed-in user can open the chat experience and see only their own history. The admin pages (where documents are ingested, removed, and application settings are changed) are meant for a smaller group. Because the platform attests each caller's identity before the request reaches the app, you control admin access at the identity provider rather than inside the application. Choose one of these approaches:

- **Require an app role or group.** Define an app role (for example, `Admin`) on the app registration, assign it to your administrators, and require that role or a security group at the identity provider so only its members can sign in. Only members of that role or group can sign in and reach the app, including its admin pages, so the admin surface stays closed to everyone else. The app does not vary what it renders by role; access is enforced entirely at the identity provider.
- **Restrict how the backend is reached.** Keep the backend reachable only from the web app's own origin or a private network, so the admin routes cannot be called directly by arbitrary clients.

Use either approach on its own or both together. Both keep the admin surface closed to the general audience while leaving chat open to every signed-in user.

## How sign-in works

Once an identity provider is configured, the platform signs the user in and exposes the signed-in principal to the web app at the `/.auth/me` endpoint on the app's own origin. The app reads the user's stable identifier from that principal and forwards it on every API call, which is how each person's chat history stays isolated. That forwarded identifier is a partition key for history, not a security boundary; the real check is the identity provider at the platform, which attests and injects the caller's identity before any request reaches the app. When no identity provider is present, the app falls back to a shared default user, which is why local development needs no sign-in setup.
