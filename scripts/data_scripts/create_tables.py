key_vault_name = 'kv_to-be-replaced'

import pandas as pd
# import pymssql
import os
from datetime import datetime

import urllib.parse
import psycopg2

from azure.keyvault.secrets import SecretClient  
from azure.identity import DefaultAzureCredential 

def get_secrets_from_kv(kv_name, secret_name):
    key_vault_name = kv_name  # Set the name of the Azure Key Vault  
    credential = DefaultAzureCredential()
    secret_client = SecretClient(vault_url=f"https://{key_vault_name}.vault.azure.net/", credential=credential)  # Create a secret client object using the credential and Key Vault name  
    return(secret_client.get_secret(secret_name).value) # Retrieve the secret value  

#TODO change connectivity with SFI 
server = get_secrets_from_kv(key_vault_name,"POSTGRESQL-SERVER")
database = get_secrets_from_kv(key_vault_name,"POSTGRESQL-DATABASENAME")
username = get_secrets_from_kv(key_vault_name,"POSTGRESQL-USER")
password = get_secrets_from_kv(key_vault_name,"POSTGRESQL-PASSWORD")
sslmode = 'require'

# Construct connection URI
db_uri = f"postgresql://{username}:{password}@{server}/{database}?sslmode={sslmode}"
# conn = pymssql.connect(server, username, password, database)

conn = psycopg2.connect(db_uri) 
print("Connection established")

cursor = conn.cursor()

from azure.storage.filedatalake import (
    DataLakeServiceClient
)

account_name = get_secrets_from_kv(key_vault_name, "ADLS-ACCOUNT-NAME")
account_key = get_secrets_from_kv(key_vault_name, "ADLS-ACCOUNT-KEY")

account_url = f"https://{account_name}.dfs.core.windows.net"

service_client = DataLakeServiceClient(account_url, credential=account_key,api_version='2023-01-03') 

file_system_client_name = "data"
directory = 'clientdata' 

file_system_client = service_client.get_file_system_client(file_system_client_name)  
directory_name = directory

cursor = conn.cursor()

#TODO CWYD POSTGRES TABLES

cursor.execute('DROP TABLE IF EXISTS conversations')
conn.commit()

create_cs_sql = """CREATE TABLE conversations (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    created_at TEXT,
                    updated_at TEXT,
                    user_id TEXT NOT NULL,
                    title TEXT
                );"""

cursor.execute(create_cs_sql)
conn.commit()

cursor = conn.cursor()

cursor.execute('DROP TABLE IF EXISTS messages')
conn.commit()

create_cs_sql = """CREATE TABLE messages (
                    id TEXT PRIMARY KEY,
                    type VARCHAR(50) NOT NULL,
                    created_at TEXT,
                    updated_at TEXT,
                    user_id TEXT NOT NULL,
                    conversation_id TEXT NOT NULL,
                    role VARCHAR(50),
                    content TEXT NOT NULL,
                    feedback TEXT
                );"""

cursor.execute(create_cs_sql)
conn.commit()
