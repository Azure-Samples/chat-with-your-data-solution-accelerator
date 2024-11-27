# Set Up Authentication in Azure App Service

## Step 1: Add Authentication in Azure App Service configuration

1. Click on `Authentication` from left menu.

![Authentication](images/AppAuthentication.png)

2. Click on `+ Add Provider` to see a list of identity providers.

![Authentication Identity](images/AppAuthenticationIdentity.png)

3. Click on `+ Add Provider` to see a list of identity providers.

![Add Provider](images/AppAuthIdentityProvider.png)

4. Select the first option `Microsoft Entra Id` from the drop-down list. If `Create new app registration` is disabled, go to [Step 1a](#step-1a-creating-a-new-app-registration).

![Add Provider](images/AppAuthIdentityProviderAdd.png)

5. Accept the default values and click on `Add` button to go back to the previous page with the identify provider added.

![Add Provider](images/AppAuthIdentityProviderAdded.png)

### Step 1a: Creating a new App Registration

1. Click on `Home` and select `Microsoft Entra ID`.

![Microsoft Entra ID](images/MicrosoftEntraID.png)

2. Click on `App registrations`.

![App registrations](images/Appregistrations.png)

3. Click on `+ New registration`.

![New Registrations](images/NewRegistration.png)

4. Provide the `Name`, select supported account types as `Accounts in this organizational directory only(Contoso only - Single tenant)`, select platform as `Web`, enter/select the `URL` and register.

![Add Details](images/AddDetails.png)

5. After application is created sucessfully, then click on `Add a Redirect URL`.

![Redirect URL](images/AddRedirectURL.png)

6. Click on `+ Add a platform`.

![+ Add platform](images/AddPlatform.png)

7. Click on `Web`.

![Web](images/Web.png)

8. Enter the `web app URL` (Provide the app service name in place of XXXX) and Save. Then go back to [Step 1](#step-1-add-authentication-in-azure-app-service-configuration) and follow from _Point 4_ choose `Pick an existing app registration in this directory` from the Add an Identity Provider page and provide the newly registered App Name.
E.g. https://appservicename.azurewebsites.net/.auth/login/aad/callback

![Add Details](images/WebAppURL.png)
