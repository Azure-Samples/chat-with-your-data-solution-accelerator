# Test Automation for Chat with your Data Accelerator



Write end-to-end tests for your web apps with [Playwright](https://github.com/microsoft/playwright-python) and [pytest](https://docs.pytest.org/en/stable/).

- Support for **all modern browsers** including Chromium, WebKit and Firefox.
- Support for **headless and headed** execution.
- **Built-in fixtures** that provide browser primitives to test functions.


Pre-Requisites:
- Install Visual Studio Code: Download and Install Visual Studio Code(VSCode).
- Install NodeJS: Download and Install Node JS

Create and Activate Python Virtual Environment
- From your directory open and run cmd : "python -m venv microsoft"
This will create a virtual environment directory named microsoft inside your current directory
- To enable virtual environment, copy location for "microsoft\Scripts\activate.bat" and run from cmd


Installing Playwright Pytest from Virtual Environment
- To install libraries run "pip install -r requirements.txt"

Run test cases
- To run test cases from your 'tests\e2e-test' folder : "pytest --headed --html=report/report.html"

Steps need to be followed to enable Access Token and Client Credentials
- Go to App Service from the resource group and select the Access Tokens check box in 'Manage->Authentication' tab
<!-- ![img.png](img.png) -->
- Go to Manage->Certificates & secrets tab to generate Client Secret value
<!-- ![img_1.png](img_1.png) -->
- Go to Overview tab to get the client id and tenant id.

Create .env file in project root level with web app url and client credentials
- create a .env file in project root level and add your user_name, pass_word, client_id,client_secret,
        tenant_id, web_url and admin_url for the resource group. please refer 'sample_dotenv_file.txt' file.

## Documentation
See on [playwright.dev](https://playwright.dev/python/docs/test-runners) for examples and more detailed information.
