# To enable ssh & remote debugging on app service change the base image to the one below
# FROM mcr.microsoft.com/azure-functions/python:4-python3.11-appservice
FROM mcr.microsoft.com/azure-functions/python:4-python3.11

ENV AzureWebJobsScriptRoot=/home/site/wwwroot \
    AzureFunctionsJobHost__Logging__Console__IsEnabled=true

COPY ./extensions/backend/requirements.txt /
RUN pip install -r /requirements.txt

COPY ./extensions/backend /home/site/wwwroot
COPY ./code/backend/batch/utilities /home/site/wwwroot/utilities