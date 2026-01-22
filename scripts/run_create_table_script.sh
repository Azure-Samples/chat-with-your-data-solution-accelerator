#!/bin/bash
echo "started the script"

# Variables
baseUrl="$1"
requirementFile="requirements.txt"
requirementFileUrl=${baseUrl}"scripts/data_scripts/requirements.txt"
resourceGroup="$2"
serverName="$3"
managedIdentityName="$4"
vectorDimensions="$5"

echo "Script Started"

# Get the public IP address of the machine running the script
publicIp=$(curl -s https://api.ipify.org)

# Use Azure CLI to add the public IP to the PostgreSQL firewall rule
az postgres flexible-server firewall-rule create --resource-group $resourceGroup --name $serverName --rule-name "AllowScriptIp" --start-ip-address "$publicIp" --end-ip-address "$publicIp"

# Download the create table python file
curl --output "create_postgres_tables.py" ${baseUrl}"scripts/data_scripts/create_postgres_tables.py"
curl --output "azure_credential_utils.py" ${baseUrl}"scripts/data_scripts/azure_credential_utils.py"

# Download the requirement file
curl --output "$requirementFile" "$requirementFileUrl"

echo "Download completed"

# Replace placeholders in the python script with actual values
sed -i "s/managedIdentityName/${managedIdentityName}/g" "create_postgres_tables.py"
sed -i "s/serverName/${serverName}/g" "create_postgres_tables.py"
sed -i "s/vectorDimensions/${vectorDimensions}/g" "create_postgres_tables.py"

pip install -r requirements.txt

python create_postgres_tables.py
