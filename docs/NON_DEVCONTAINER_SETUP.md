[Back to *Chat with your data* README](../README.md)

# Project setup

If you are unable to run this accelerator as a DevContainer or in CodeSpaces, then you will need.

- [Visual Studio Code](https://code.visualstudio.com/)
    - Extensions
        - [Azure Functions](https://marketplace.visualstudio.com/items?itemName=ms-azuretools.vscode-azurefunctions)
        - [Azure Tools](https://marketplace.visualstudio.com/items?itemName=ms-vscode.vscode-node-azure-pack)
        - [Bicep](https://marketplace.visualstudio.com/items?itemName=ms-azuretools.vscode-bicep)
        - [Pylance](https://marketplace.visualstudio.com/items?itemName=ms-python.vscode-pylance)
        - [Python](https://marketplace.visualstudio.com/items?itemName=ms-python.python)
        - [Teams Toolkit](https://marketplace.visualstudio.com/items?itemName=TeamsDevApp.ms-teams-vscode-extension) (optional: Teams extension only)
- Install [Node.js](https://nodejs.org/en)
  - Install the LTS version (Recommended for Most Users)


### Running the sample using the Azure Developer CLI (azd)

The Azure Developer CLI (`azd`) is a developer-centric command-line interface (CLI) tool for creating Azure applications.

You need to install it before running and deploying with the Azure Developer CLI. (If you use the devcontainer, everything is already installed)

### Windows

```powershell
powershell -ex AllSigned -c "Invoke-RestMethod 'https://aka.ms/install-azd.ps1' | Invoke-Expression"
```

### Linux/MacOS

```
curl -fsSL https://aka.ms/install-azd.sh | bash
```

After logging in with the following command, you will be able to use the `azd` cli to quickly provision and deploy the application.

```
azd auth login
```

Then, execute the `azd init` command to initialize the environment (You do not need to run this command if you already have the code or have opened this in a Codespace or DevContainer).
```
azd init -t chat-with-your-data-solution-accelerator
```
Enter an environment name.

Then, run `azd up` to provision all the resources to Azure and deploy the code to those resources.
```
azd up 
```

Select your desired `subscription` and `location`. Wait a moment for the resource deployment to complete, click the website endpoint and you will see the web app page.
