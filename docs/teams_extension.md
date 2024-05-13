[Back to *Chat with your data* README](../README.md)

# Teams extension
[**USER STORY**](#user-story) | [**TEAMS DEPLOY**](#deployment-to-teams) | [**SUPPORTING DOCUMENTATION**](#supporting-documentation)
\
\
![User Story](images/userStory.png)
## User story
This extension enables users to experience Chat with your data within Teams, without having to switch platforms. It allows them to stay within their existing workflow and get the answers they need. Instead of building the Chat with your data solution accelerator from scratch within Teams, the same underlying backend used for the web application is leveraged within Teams.

![Teams - Chat with your Data](images/teams-cwyd.png)

## Deployment to Teams
**IMPORTANT**: Before you proceed, installation and configuration of the [Chat with your data with speech-to-text deployment](../README.md) is required.

### Pre-requisites
- [Visual Studio Code](https://code.visualstudio.com/)
    - Extensions
        - [Teams Toolkit](https://marketplace.visualstudio.com/items?itemName=TeamsDevApp.ms-teams-vscode-extension) (optional: Teams extension only)
- Install [Node.js](https://nodejs.org/en)
  - Install the LTS version (Recommended for Most Users)
- [Enable custom Teams apps and turn on custom app uploading](https://learn.microsoft.com/en-us/microsoftteams/platform/concepts/build-and-test/prepare-your-o365-tenant#enable-custom-teams-apps-and-turn-on-custom-app-uploading) (optional: Teams extension only)
- In order to publish the App to the Teams Store, the Teams Administrator role is required.

### Deploy Teams application
1. Clone this GitHub repo.
2. Open the “extensions/teams” folder with Visual Studio Code

![Teams](images/teams.png)

3. Open the file env\\.env.test

![ENV](images/teams-1.png)

4. Locate the environment variable _AZURE_FUNCTION_URL_.
5. Replace the `<RESOURCE_TOKEN>`  and `<FUNCTION_APP_CLIENT_KEY>` with the name of your Function App resource and its clientKey (created in previous section)
    ```env
    AZURE_FUNCTION_URL=https://backend-<RESOURCE_TOKEN>.azurewebsites.net/api/GetConversationResponse?code=<FUNCTION_APP_CLIENT_KEY>&clientId=clientKey

    ```
    ![Env](images/teams-deploy-env.png)
6. Save the file.
7. Select Teams Toolkit from the navigation panel.

![Teams Toolkit in VS Code](images/teams-2.png)

8. Within the Teams Toolkit panel, login to the following accounts:

  **Sign in to Microsoft 365**: Use your Microsoft 365 work or school account with a valid E5 subscription for building your app. If you don't have a valid account, you can join [Microsoft 365 developer program](https://developer.microsoft.com/microsoft-365/dev-program) to get a free account before you start.

  **Sign in to Azure**: Use your Azure account for deploying your app on Azure. You can [create a free Azure account](https://azure.microsoft.com/free/) before you start.

![Teams Toolkit Accounts](images/teams-3.png)

9. Under **Environment**, select **test**.

![Teams Toolkit Environment](images/teams-4.png)

10. Under **Lifecycle**, select **Provision**.

![Teams Toolkit Lifecycle Provision](images/teams-5.png)

11. Within the command palette, select **test** for the environment.

![Select an Environment](images/teams-6.png)

12. Select the resource group created earlier in the installation

![Select a Resource Group](images/teams-7.png)

13. When prompted about Azure charges, select **Provision**.

![Azure Charges Prompt](images/teams-8.png)

14. Verify that the provisioning was successful.

![Provision Successful](images/teams-9.png)

15. Under **Lifecycle**, select **Deploy**.

![Teams Toolkit Lifecycle Deploy](images/teams-10.png)

16. Within the command palette, select **test** for the environment.

![Select an Environment](images/teams-6.png)

17. When prompted, select **Deploy**.

![VS Code Prompt to Deploy](images/teams-11.png)

18. Verify that the Deployment was successful.

![Deployment successful](images/teams-12.png)

19. Under **Lifecycle**, select **Publish**.

![Teams Toolkit Lifecycle Publish](images/teams-13.png)

20. Within the command palette, select **test** for the environment.

![Select an Environment](images/teams-6.png)

21. Verify that the Publish was successful.

![Publishing successful](images/teams-14.png)

22. Select **Go to admin portal**.

![Go to Admin Portal](images/teams-15.png)

23. On the Manage apps page within the Teams Admin portal, you should see one submitted custom app pending approval.

![Pending Approval](images/teams-16.png)

24. In the search by name input box, enter: **enterprise chat**

![Filtered app](images/teams-17.png)

25. Select the app and then select **Allow**.

![Selected app](images/teams-18.png)

26. Select the app name.

![Select app name](images/teams-19.png)

27. Select **Publish**.

![Publish app](images/teams-20.png)

28. When prompted, select **Publish**.

![Prompt to publish](images/teams-21.png)

29. Depending on your environment, it may take several hours to publish.

![Teams Publish Success](images/teams-22.png)


### [Local deployment instructions](TEAMS_LOCAL_DEPLOYMENT.md)
To customize the accelerator or run it locally, first, copy the .env.sample file to your development environment's .env file, and edit it according to environment variable values table. Learn more about deploying locally [here](TEAMS_LOCAL_DEPLOYMENT.md).
\
\
![Supporting documentation](images/supportingDocuments.png)

## Supporting documentation
### Resource links for Teams extension
This solution accelerator deploys the following resources. It's crucial to comprehend the functionality of each. Below are the links to their respective documentation:
- [Bots in Microsoft Teams - Teams | Microsoft Learn](https://learn.microsoft.com/en-us/microsoftteams/platform/bots/what-are-bots)
