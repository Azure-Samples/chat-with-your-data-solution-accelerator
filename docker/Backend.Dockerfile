FROM mcr.microsoft.com/azure-functions/python:4-python3.11

ENV AzureWebJobsScriptRoot=/home/site/wwwroot \
    AzureFunctionsJobHost__Logging__Console__IsEnabled=true \
    AzureWebJobsFeatureFlags=EnableWorkerIndexing

COPY pyproject.toml /
COPY poetry.lock /
RUN pip install --upgrade pip && pip install poetry && poetry self add poetry-plugin-export && poetry export -o requirements.txt && pip install -r requirements.txt

COPY ./code/backend/batch/utilities /home/site/wwwroot/utilities
COPY ./code/backend/batch /home/site/wwwroot
