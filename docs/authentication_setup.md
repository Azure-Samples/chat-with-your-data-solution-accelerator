---
title: Set up authentication
description: Secure Chat with Your Data with Microsoft Entra ID — a browser-side MSAL (PKCE) sign-in on the frontend SPA and Azure Container Apps built-in authentication validating the token on the backend.
ms.date: 2026-10-06
ms.topic: how-to
---

[Back to *Chat with your data* README](../README.md)

![Supporting documentation](images/supportingDocuments.png)

# Set Up Authentication in Azure Container Apps

The frontend (`ca-frontend-<suffix>`) and backend (`ca-backend-<suffix>`) run as **separate** Container Apps, each with its own public ingress. The browser calls the backend directly, so the backend must validate every request: securing only the frontend leaves the backend admin API (`/api/admin/*`) reachable by anonymous callers — who could read or change configuration, disable content safety, or modify the indexed corpus.

Authentication is **secretless**. The frontend SPA signs the user in with **MSAL** (authorization code + PKCE — a public client, no client secret). It acquires a Microsoft Entra ID token whose audience is the shared app registration's client id, and forwards it as an `Authorization: Bearer` header on every backend call. The backend Container App's built-in authentication (Easy Auth) validates that token (bearer validation only — again, no secret) and injects the trusted `x-ms-client-principal-id` header the backend uses for per-user partitioning and the admin-auth gate.

## Recommended: run the setup script (configures both apps)

After `azd up` and `az login`, run the authentication script. In a single run it:

- creates (or reuses) one Entra app registration shared by both Container Apps;
- registers the frontend **SPA redirect URI** (PKCE public client) on that app registration;
- disables ingress Easy Auth on the **frontend** so the SPA loads anonymously and signs in via MSAL, and sets the MSAL parameters (`AZURE_AUTH_CLIENT_ID`, `AZURE_TENANT_ID`) the SPA reads at runtime from `/config`;
- enables Easy Auth on the **backend** Container App with the unauthenticated action set to **return 401**, validating the MSAL id token whose audience is the app's client id — no client secret stored;
- turns on the backend's in-app admin-auth gate (`AZURE_REQUIRE_ADMIN_AUTH=true`);
- records the backend audience and the frontend CORS origin in the azd environment; and
- verifies that an anonymous admin call is rejected (with retry for propagation).

```powershell
# PowerShell
.\infra\scripts\post-provision\setup_auth.ps1 -ResourceGroupName "<RESOURCE_GROUP>"
```

```bash
# Bash
bash infra/scripts/post-provision/setup_auth.sh "<RESOURCE_GROUP>"
```

The script is idempotent — safe to re-run. It needs an Azure CLI session whose account can configure the Container Apps and create/read an Entra app registration (**Application Developer** or **Application Administrator** directory role). If it cannot create the registration, it prints the name a directory admin should create, then reuses it on the next run.

After it finishes, reload the SPA; it redirects you to Microsoft Entra sign-in on first load, then returns to the app authenticated.

### Verify

The script checks this automatically. To re-check manually, an anonymous request to the backend admin API must be rejected:

```bash
curl -i "https://<backend-fqdn>/api/admin/status"
# Expected: HTTP/1.1 401 Unauthorized
```

### Local development

The backend's in-app gate is controlled by `AZURE_REQUIRE_ADMIN_AUTH` (default `true`, secure by default). On a local loopback stack with no identity provider, set `AZURE_REQUIRE_ADMIN_AUTH=false` to restore anonymous access for development. The SPA skips MSAL sign-in whenever `/config` returns no `authClientId` (the local-dev default), falling back to the anonymous default user. Never set `AZURE_REQUIRE_ADMIN_AUTH=false` on a public deployment.

## Alternative: register the SPA redirect URI in the portal

The setup script registers the SPA redirect URI automatically via Microsoft Graph. If that step is blocked (for example, insufficient directory permissions), add it by hand in the portal, then re-run the script to finish securing the backend.

1. Open the shared app registration in **Microsoft Entra ID → App registrations** (named `ca-backend-<suffix>-auth`).

2. Select **Authentication** from the left menu, then **+ Add a platform**.

3. Choose **Single-page application**.

4. Set the redirect URI to the frontend origin, `https://ca-frontend-<suffix>.<region>.azurecontainerapps.io` (no path), and select **Configure**.

5. Save. The SPA platform enables the authorization-code + PKCE flow with no client secret. Re-run the setup script to confirm the backend rejects anonymous admin calls.