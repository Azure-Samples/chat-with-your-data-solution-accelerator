[Back to *Chat with your data* README](../README.md)

# Non-DevContainer Setup

If you are unable to run this accelerator using a DevContainer or in GitHub CodeSpaces, then you will need to install the following prerequisites on your local machine.

- A code editor. We recommend [Visual Studio Code](https://code.visualstudio.com/), with the following extensions:
  - [Azure Functions](https://marketplace.visualstudio.com/items?itemName=ms-azuretools.vscode-azurefunctions)
  - [Azure Tools](https://marketplace.visualstudio.com/items?itemName=ms-vscode.vscode-node-azure-pack)
  - [Bicep](https://marketplace.visualstudio.com/items?itemName=ms-azuretools.vscode-bicep)
  - [Pylance](https://marketplace.visualstudio.com/items?itemName=ms-python.vscode-pylance)
  - [Python](https://marketplace.visualstudio.com/items?itemName=ms-python.python)
  - [Teams Toolkit](https://marketplace.visualstudio.com/items?itemName=TeamsDevApp.ms-teams-vscode-extension) **Optional**
- [Python 3.11](https://www.python.org/downloads/release/python-3119/)
- [Node.js LTS](https://nodejs.org/en)
- [Azure Developer CLI](https://learn.microsoft.com/en-us/azure/developer/azure-developer-cli/install-azd)
- [Azure Functions Core Tools](https://docs.microsoft.com/en-us/azure/azure-functions/functions-run-local)

## Setup

1. Configure your Python environment:

    ```bash
    pip install --upgrade pip

    pip install poetry

    # https://pypi.org/project/poetry-plugin-export/
    pip install poetry-plugin-export

    poetry env use python3.11

    poetry config warnings.export false

    poetry install --with dev
    ```

1. Install `pre-commit` Git hooks:

    ```bash
    poetry run pre-commit install
    ```

1. Install Node.js dependencies:

    ```bash
    (cd ./code/frontend; npm install)

    (cd ./tests/integration/ui; npm install)
    ```

1. Select the Python interpreter in Visual Studio Code:

    - Open the command palette (`Ctrl+Shift+P` or `Cmd+Shift+P`).
    - Type `Python: Select Interpreter`.
    - Select the Python 3.11 environment created by Poetry.

### Running the sample using the Azure Developer CLI (azd)

The Azure Developer CLI (`azd`) is a developer-centric command-line interface (CLI) tool for creating Azure applications.

1. Log in to Azure using `azd`:

  ```
  azd auth login
  ```

1. Execute the `azd init` command to initialize the environment and enter the solution accelerator name when prompted:

  ```
  azd init -t chat-with-your-data-solution-accelerator
  ```

1. Run `azd up` to provision all the resources to Azure and deploy the code to those resources.

  ```
  azd up
  ```

  > Select your desired `subscription` and `location`. Wait a moment for the resource deployment to complete, click the website endpoint and you will see the web app page.
