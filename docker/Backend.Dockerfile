FROM mcr.microsoft.com/azure-functions/python:4-python3.11

ENV AzureWebJobsScriptRoot=/home/site/wwwroot \
    AzureFunctionsJobHost__Logging__Console__IsEnabled=true \
    AzureWebJobsFeatureFlags=EnableWorkerIndexing

COPY pyproject.toml /
COPY uv.lock /
RUN pip install --upgrade pip && pip install uv && uv export --no-hashes -o requirements.txt && pip install -r requirements.txt

COPY ./src/functions /home/site/wwwroot
COPY ./src/shared /home/site/wwwroot/shared
