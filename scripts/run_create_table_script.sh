#!/bin/bash
echo "started the script"

# Variables
baseUrl="$1"
keyvaultName="$2"
requirementFile="requirements.txt"
requirementFileUrl=${baseUrl}"scripts/data_scripts/requirements.txt"

echo "Script Started"

# Download the create table python file
curl --output "create_postgres_tables.py" ${baseUrl}"scripts/data_scripts/create_postgres_tables.py"

# Download the requirement file
curl --output "$requirementFile" "$requirementFileUrl"

echo "Download completed"

#Replace key vault name
sed -i "s/kv_to-be-replaced/${keyvaultName}/g" "create_postgres_tables.py"

pip install -r requirements.txt

pip show azure-identity

python create_postgres_tables.py
