---
title: Check quota availability
description: Verify Azure OpenAI model quota in Azure AI Foundry before deploying Chat with Your Data.
ms.date: 2026-07-03
ms.topic: how-to
---

[Back to *Chat with your data* README](../README.md)

![Supporting documentation](images/supportingDocuments.png)

## Check Quota Availability Before Deployment

Before deploying the accelerator, **ensure sufficient quota availability** for the Azure OpenAI model deployed to Azure AI Foundry.

> **For Global Standard GPT-5.1, ensure at least 150k tokens of capacity post-deployment for optimal performance.**

The quota-check script (`quota_check_params.sh`) is provided by the upstream [chat-with-your-data-solution-accelerator](https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator/blob/main/scripts/quota_check_params.sh) repository. This fork does not vendor a local copy, so the steps below download it before running.

### Login if you have not done so already
```
azd auth login
```


### 📌 Default Models & Capacities:
```
gpt-5.1:150, text-embedding-3-large:100
```
### 📌 Default Regions:
```
australiaeast, eastus2, japaneast, uksouth
```
### Usage Scenarios:
- No parameters passed → Default models and capacities will be checked in default regions.
- Only model(s) provided → The script will check for those models in the default regions.
- Only region(s) provided → The script will check default models in the specified regions.
- Both models and regions provided → The script will check those models in the specified regions.
- `--verbose` passed → Enables detailed logging output for debugging and traceability.

### **Input Formats**
> Use the --models, --regions, and --verbose options for parameter handling:

✔️ Run without parameters to check default models & regions without verbose logging:
   ```
  ./quota_check_params.sh
   ```
✔️ Enable verbose logging:
   ```
  ./quota_check_params.sh --verbose
   ```
✔️ Check specific model(s) in default regions:
  ```
  ./quota_check_params.sh --models gpt-5.1:150,text-embedding-3-large:100
  ```
✔️ Check default models in specific region(s):
```
./quota_check_params.sh --regions eastus2,japaneast
```
✔️ Passing both models and regions:
```
./quota_check_params.sh --models gpt-5.1:150 --regions eastus2,japaneast
```
✔️ All parameters combined:
```
./quota_check_params.sh --models gpt-5.1:150,text-embedding-3-large:100 --regions eastus2,japaneast --verbose
```

### **Sample Output**
The final table lists regions with available quota. You can select any of these regions for deployment.

![quota-check-output](images/quota-check-output.png)

---
### **If using Azure Portal and Cloud Shell**

1. Navigate to the [Azure Portal](https://portal.azure.com).
2. Click on **Azure Cloud Shell** in the top right navigation menu.
3. Run the appropriate command based on your requirement:

   **To check quota for the deployment**

    ```sh
    curl -L -o quota_check_params.sh "https://raw.githubusercontent.com/Azure-Samples/chat-with-your-data-solution-accelerator/main/scripts/quota_check_params.sh"
    chmod +x quota_check_params.sh
    ./quota_check_params.sh
    ```
    - Refer to [Input Formats](#input-formats) for detailed commands.

### **If using VS Code or Codespaces**
1. Open the terminal in VS Code or Codespaces.
2. If you're using VS Code, click the dropdown on the right side of the terminal window, and select `Git Bash`.
   ![git_bash](images/git_bash.png)
3. Download the quota-check script and make it executable:
   ```sh
    curl -L -o quota_check_params.sh "https://raw.githubusercontent.com/Azure-Samples/chat-with-your-data-solution-accelerator/main/scripts/quota_check_params.sh"
    chmod +x quota_check_params.sh
    ```
4. Run the appropriate script based on your requirement:

   **To check quota for the deployment**

    ```sh
    ./quota_check_params.sh
    ```
   - Refer to [Input Formats](#input-formats) for detailed commands.

5. If you see the error `_bash: az: command not found_`, install Azure CLI:

    ```sh
    curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
    az login
    ```
6. Rerun the script after installing Azure CLI.

> **Note:** The regions listed above (australiaeast, eastus2, japaneast, uksouth) are the defaults the quota-check script inspects. They are examples, not a hard restriction, and were chosen because they commonly support the required models and paired-region data redundancy. Model and capacity availability can vary by region, so verify current availability for your subscription and pass your own `--regions` values if you want to deploy elsewhere.

## Related documentation

* [Deploy with azd](LOCAL_DEPLOYMENT.md)
* [Azure OpenAI model quota settings](azure_openai_model_quota_settings.md)
* [Troubleshooting](TroubleShootingSteps.md)
