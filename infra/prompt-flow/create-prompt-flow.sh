#!/bin/bash

set -e

SCRIPTPATH="$( cd -- "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )"

echo "Assigning variables from azd env"

while IFS='=' read -r key value; do
    value=$(echo "$value" | sed 's/^"//' | sed 's/"$//')
    case "$key" in
        "ORCHESTRATION_STRATEGY") orchestration_strategy=$value ;;
        "AZURE_SUBSCRIPTION_ID") subscription_id=$value ;;
        "AZURE_TENANT_ID") tenant_id=$value ;;
        "AZURE_RESOURCE_GROUP") resource_group=$value ;;
        "AZURE_ML_WORKSPACE_NAME") aml_workspace=$value ;;
        "RESOURCE_TOKEN") resource_token=$value ;;
        "AZURE_OPENAI_RESOURCE") openai_resource=$value ;;
        "AZURE_OPENAI_EMBEDDING_MODEL") openai_embedding_model=$value ;;
        "AZURE_SEARCH_SERVICE") search_service=$value ;;
        "AZURE_SEARCH_INDEX") search_index=$value ;;
    esac
done <<EOF
$(azd env get-values)
EOF

if [ "$orchestration_strategy" != "prompt_flow" ]; then
    echo "Orchestration strategy is not prompt_flow, skipping prompt flow creation"
    exit 0
fi

if [ -z "$subscription_id" ] || [ -z "$resource_group" ] || [ -z "$aml_workspace" ] || [ -z "$resource_token" ] || [ -z "$openai_resource" ] || [ -z "$openai_embedding_model" ] || [ -z "$search_service" ] || [ -z "$search_index" ]; then
    echo "AZURE_SUBSCRIPTION_ID, AZURE_RESOURCE_GROUP, AZURE_ML_WORKSPACE_NAME, RESOURCE_TOKEN, AZURE_OPENAI_RESOURCE, AZURE_OPENAI_EMBEDDING_MODEL, AZURE_SEARCH_SERVICE and AZURE_SEARCH_INDEX must be set in azd env"
    echo "AZURE_SUBSCRIPTION_ID=$subscription_id"
    echo "AZURE_RESOURCE_GROUP=$resource_group"
    echo "AZURE_ML_WORKSPACE_NAME=$aml_workspace"
    echo "RESOURCE_TOKEN=$resource_token"
    echo "AZURE_OPENAI_RESOURCE=$openai_resource"
    echo "AZURE_OPENAI_EMBEDDING_MODEL=$openai_embedding_model"
    echo "AZURE_SEARCH_SERVICE=$search_service"
    echo "AZURE_SEARCH_INDEX=$search_index"
    exit 1
fi

model_name="cwyd-model-${resource_token}"
endpoint_name="cwyd-endpoint-${resource_token}"
deployment_name="cwyd-deployment-${resource_token}"

echo "Installing dependencies"
poetry install --only prompt-flow
az extension add --name ml

echo "Creating prompt flow"
flow_dir="${SCRIPTPATH}/cwyd"
flow_dag_file="${flow_dir}/flow.dag.yaml"
cp "${SCRIPTPATH}/cwyd/flow.dag.template.yaml" "$flow_dag_file"

connection_id_prefix="/subscriptions/${subscription_id}/resourceGroups/${resource_group}/providers/Microsoft.MachineLearningServices/workspaces/${aml_workspace}/connections"

sed -i "s@<openai_api_base>@https://${openai_resource}.openai.azure.com/@g" "$flow_dag_file"
sed -i "s@<openai_connection_id>@${connection_id_prefix}/openai_connection@g" "$flow_dag_file"
sed -i "s@<openai_embedding_model>@${openai_embedding_model}@g" "$flow_dag_file"
sed -i "s@<aisearch_connection_id>@${connection_id_prefix}/aisearch_connection@g" "$flow_dag_file"
sed -i "s@<aisearch_endpoint>@${search_service}@g" "$flow_dag_file"
sed -i "s@<aisearch_index>@${search_index}@g" "$flow_dag_file"

# login to Azure if not already logged in
az account show > /dev/null 2>&1 || az login --tenant "$tenant_id"
az account set --subscription "$subscription_id"

set +e
tries=1
pfazure flow create --subscription "$subscription_id" --resource-group "$resource_group" \
    --workspace-name "$aml_workspace" --flow "$flow_dir" --set type=chat
while [ $? -ne 0 ]; do
    tries=$((tries+1))
    if [ $tries -eq 10 ]; then
        echo "Failed to create flow after 10 attempts"
        exit 1
    fi

    echo "Failed to create flow, will retry in 30 seconds"
    sleep 30
    pfazure flow create --subscription "$subscription_id" --resource-group "$resource_group" \
        --workspace-name "$aml_workspace" --flow "$flow_dir" --set type=chat
done
set -e

echo "Creating model"
az ml model create --file "${SCRIPTPATH}/model.yaml" --resource-group "$resource_group" --workspace-name "$aml_workspace" --set "name=$model_name"

if az ml online-endpoint show  --resource-group "$resource_group"  --workspace-name "$aml_workspace" --name "$endpoint_name" > /dev/null 2>&1; then
    echo "Updating endpoint"
    az ml online-endpoint update --resource-group "$resource_group" --workspace-name "$aml_workspace" --file "${SCRIPTPATH}/endpoint.yaml" --set "name=$endpoint_name" --set auth_mode=key
else
    echo "Creating endpoint"
    az ml online-endpoint create --resource-group "$resource_group" --workspace-name "$aml_workspace" --file "${SCRIPTPATH}/endpoint.yaml" --set "name=$endpoint_name" --set auth_mode=key
fi

endpoint_id=$(az ml online-endpoint show --resource-group "$resource_group" --workspace-name "$aml_workspace"  --name "$endpoint_name" --query "identity.principal_id" --output tsv)
az role assignment create --role "Azure Machine Learning Workspace Connection Secrets Reader" --scope "/subscriptions/${subscription_id}/resourceGroups/${resource_group}/providers/Microsoft.MachineLearningServices/workspaces/${aml_workspace}" --assignee-object-id "$endpoint_id" --assignee-principal-type ServicePrincipal

prt_config_override="deployment.subscription_id=${subscription_id},deployment.resource_group=${resource_group},deployment.workspace_name=${aml_workspace},deployment.endpoint_name=${endpoint_name},deployment.deployment_name=${deployment_name}"
model_version=$(az ml model list --resource-group "$resource_group" --workspace-name "$aml_workspace" --name "$model_name" --query "[].version | max(@)" --output tsv)
if az ml online-deployment show  --resource-group "$resource_group"  --workspace-name "$aml_workspace" --endpoint-name "$endpoint_name" --name "$deployment_name" > /dev/null 2>&1; then
    echo "Updating deployment"
    az ml online-deployment update --file "${SCRIPTPATH}/deployment.yaml" --resource-group "$resource_group" --workspace-name "$aml_workspace" --set "name=$deployment_name" --set "endpoint_name=$endpoint_name" --set "model=azureml:${model_name}:${model_version}" --set environment_variables={} --set "environment_variables.PRT_CONFIG_OVERRIDE=$prt_config_override" --set environment_variables.PROMPTFLOW_RUN_MODE=serving
else
    echo "Creating deployment"
    az ml online-deployment create --file "${SCRIPTPATH}/deployment.yaml" --resource-group "$resource_group" --workspace-name "$aml_workspace" --all-traffic --set "name=$deployment_name" --set "endpoint_name=$endpoint_name" --set "model=azureml:${model_name}:${model_version}" --set "environment_variables.PRT_CONFIG_OVERRIDE=$prt_config_override"
fi

rm "$flow_dag_file"
