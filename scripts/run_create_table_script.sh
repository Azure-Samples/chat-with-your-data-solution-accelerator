#!/bin/bash
echo "started the script"

# Variables
baseUrl="$1"
keyvaultName="$2"
requirementFile="requirements.txt"
requirementFileUrl=${baseUrl}"scripts/data_scripts/requirements.txt"
resourceGroup="$3"
serverName="$4"
webAppPrincipalName="$5"
adminAppPrincipalName="$6"
functionAppPrincipalName="$7"
managedIdentityName="$8"

echo "Script Started"

# Get the public IP address of the machine running the script
publicIp=$(curl -s https://api.ipify.org)

# Use Azure CLI to add the public IP to the PostgreSQL firewall rule
az postgres flexible-server firewall-rule create --resource-group $resourceGroup --name $serverName --rule-name "AllowScriptIp" --start-ip-address "$publicIp" --end-ip-address "$publicIp"

# Download the create table python file
curl --output "create_postgres_tables.py" ${baseUrl}"scripts/data_scripts/create_postgres_tables.py"

# Download the requirement file
curl --output "$requirementFile" "$requirementFileUrl"

echo "Download completed"

#Replace key vault name
sed -i "s/kv_to-be-replaced/${keyvaultName}/g" "create_postgres_tables.py"
sed -i "s/webAppPrincipalName/${webAppPrincipalName}/g" "create_postgres_tables.py"
sed -i "s/adminAppPrincipalName/${adminAppPrincipalName}/g" "create_postgres_tables.py"
sed -i "s/managedIdentityName/${managedIdentityName}/g" "create_postgres_tables.py"
sed -i "s/functionAppPrincipalName/${functionAppPrincipalName}/g" "create_postgres_tables.py"
sed -i "s/serverName/${serverName}/g" "create_postgres_tables.py"

pip install -r requirements.txt

python create_postgres_tables.py
