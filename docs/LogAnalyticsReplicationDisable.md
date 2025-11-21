# 🛠 Handling Log Analytics Workspace Deletion with Replication Enabled

If redundancy (replication) is enabled for your Log Analytics workspace, you must disable it before deleting the workspace or resource group. Otherwise, deletion will fail.

## ✅ Steps to Disable Replication Before Deletion
Run the following Azure CLI command. Note: This operation may take about 5 minutes to complete.

```bash
az resource update --ids "/subscriptions/{subscriptionId}/resourceGroups/{resourceGroupName}/providers/Microsoft.OperationalInsights/workspaces/{logAnalyticsName}" --set properties.replication.enabled=false
```

Replace:
- `{subscriptionId}` → Your Azure subscription ID
- `{resourceGroupName}` → The name of your resource group
- `{logAnalyticsName}` → The name of your Log Analytics workspace

Optional: Verify replication disabled (should output `false`):
```bash
az resource show --ids "/subscriptions/{subscriptionId}/resourceGroups/{resourceGroupName}/providers/Microsoft.OperationalInsights/workspaces/{logAnalyticsName}" --query properties.replication.enabled -o tsv
```

## ✅ After Disabling Replication
You can safely delete:
- The Log Analytics workspace (manual)
- The resource group (manual), or
- All provisioned resources via `azd down`

Return to: [Deployment Guide](./DeploymentGuide.md)
