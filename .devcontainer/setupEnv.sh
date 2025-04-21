#!/bin/bash

echo "===== [setupEnv.sh] Setting up local development environment ====="

# Ensure Docker is running
if ! docker info >/dev/null 2>&1; then
    echo "[ERROR] Docker is not running. Please start Docker Desktop."
    exit 1
fi

# Remove existing Azurite container if it exists
if docker ps -a --format '{{.Names}}' | grep -q '^azurite$'; then
    echo "Stopping and removing existing Azurite container..."
    docker stop azurite && docker rm azurite
fi

# Start a fresh Azurite container
echo "Starting new Azurite container on ports 10000-10002..."
docker run -d \
  --name azurite \
  -p 10000:10000 -p 10001:10001 -p 10002:10002 \
  mcr.microsoft.com/azure-storage/azurite

# Define Azurite connection string
#AZURITE_CONNECTION_STRING="UseDevelopmentStorage=true"
AZURITE_CONNECTION_STRING="DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFeqCnf2P==;BlobEndpoint=http://azurite:10000/devstoreaccount1;QueueEndpoint=http://azurite:10001/devstoreaccount1;TableEndpoint=http://azurite:10002/devstoreaccount1;"
# Output for confirmation
echo "Azurite started. Local connection string:"
echo "$AZURITE_CONNECTION_STRING"

echo ".env file written with local storage emulator settings."

echo "===== [setupEnv.sh] Setting up local development Environment Components Done ====="

pip install --upgrade pip

pip install poetry

# https://pypi.org/project/poetry-plugin-export/
pip install poetry-plugin-export

poetry env use python3.11

poetry config warnings.export false

poetry install --with dev

poetry run pre-commit install

(cd ./code/frontend; npm install)

(cd ./tests/integration/ui; npm install)
