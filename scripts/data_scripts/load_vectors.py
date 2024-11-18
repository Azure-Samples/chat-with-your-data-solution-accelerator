import openai
import os
import pandas as pd
import numpy as np
import json
# import tiktoken
import psycopg2
import ast
import pgvector
import math
from psycopg2.extras import execute_values
from pgvector.psycopg2 import register_vector

#TODO may this file is not needed for CWYD postgress Integration 

#Get Azure Key Vault Client
key_vault_name = 'kv_to-be-replaced'

index_name = "transcripts_index"

file_system_client_name = "data"
directory = 'clienttranscripts/meeting_transcripts' 
csv_file_name = 'clienttranscripts/meeting_transcripts_metadata/transcripts_metadata.csv'

from azure.keyvault.secrets import SecretClient  
from azure.identity import DefaultAzureCredential 

def get_secrets_from_kv(kv_name, secret_name):
    
  # Set the name of the Azure Key Vault  
  key_vault_name = kv_name 
  credential = DefaultAzureCredential()

  # Create a secret client object using the credential and Key Vault name  
  secret_client = SecretClient(vault_url=f"https://{key_vault_name}.vault.azure.net/", credential=credential)  
    
  # Retrieve the secret value  
  return(secret_client.get_secret(secret_name).value)

# openai_api_type = get_secrets_from_kv(key_vault_name,"OPENAI-API-TYPE")
openai_api_key  = get_secrets_from_kv(key_vault_name,"AZURE-OPENAI-KEY")
openai_api_base = get_secrets_from_kv(key_vault_name,"AZURE-OPENAI-ENDPOINT")
openai_api_version = get_secrets_from_kv(key_vault_name,"AZURE-OPENAI-PREVIEW-API-VERSION")

# Connect to PostgreSQL database using connection string
server = get_secrets_from_kv(key_vault_name,"POSTGRESQL-SERVER")
database = get_secrets_from_kv(key_vault_name,"POSTGRESQL-DATABASENAME")
username = get_secrets_from_kv(key_vault_name,"POSTGRESQL-USER")
password = get_secrets_from_kv(key_vault_name,"POSTGRESQL-PASSWORD")
sslmode = 'require'

# Construct connection URI
db_uri = f"postgresql://{username}:{password}@{server}/{database}?sslmode={sslmode}"

conn = psycopg2.connect(db_uri)
cur = conn.cursor()

#install pgvector 
cur = conn.cursor()
cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
conn.commit()

# Register the vector type with psycopg2
register_vector(conn)

cur.execute('DROP TABLE IF EXISTS calltranscripts;')
# Create table to store embeddings and metadata
table_create_command = """
CREATE TABLE IF NOT EXISTS calltranscripts (
            id text, 
            chunk_id text,
            content text,
            sourceurl text,
            client_id integer,
            contentVector vector(1536)
            );
            """

cur.execute(table_create_command)
cur.close()
conn.commit()

from openai import AzureOpenAI

# Function: Get Embeddings
def get_embeddings(text: str,openai_api_base,openai_api_version,openai_api_key):
    model_id = "text-embedding-ada-002"
    client = AzureOpenAI(
        api_version=openai_api_version,
        azure_endpoint=openai_api_base,
        api_key = openai_api_key
    )
    
    embedding = client.embeddings.create(input=text, model=model_id).data[0].embedding

    return embedding

import re

def clean_spaces_with_regex(text):
    # Use a regular expression to replace multiple spaces with a single space
    cleaned_text = re.sub(r'\s+', ' ', text)
    # Use a regular expression to replace consecutive dots with a single dot
    cleaned_text = re.sub(r'\.{2,}', '.', cleaned_text)
    return cleaned_text

def chunk_data(text):
    tokens_per_chunk = 1024 #500
    text = clean_spaces_with_regex(text)
    SENTENCE_ENDINGS = [".", "!", "?"]
    WORDS_BREAKS = ['\n', '\t', '}', '{', ']', '[', ')', '(', ' ', ':', ';', ',']

    sentences = text.split('. ') # Split text into sentences
    chunks = []
    current_chunk = ''
    current_chunk_token_count = 0
    
    # Iterate through each sentence
    for sentence in sentences:
        # Split sentence into tokens
        tokens = sentence.split()
        
        # Check if adding the current sentence exceeds tokens_per_chunk
        if current_chunk_token_count + len(tokens) <= tokens_per_chunk:
            # Add the sentence to the current chunk
            if current_chunk:
                current_chunk += '. ' + sentence
            else:
                current_chunk += sentence
            current_chunk_token_count += len(tokens)
        else:
            # Add current chunk to chunks list and start a new chunk
            chunks.append(current_chunk)
            current_chunk = sentence
            current_chunk_token_count = len(tokens)
    
    # Add the last chunk
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks

#add documents to the index

import json
import base64
import time
import pandas as pd
from azure.search.documents import SearchClient
import os

# foldername = 'clienttranscripts'
# path_name = f'Data/{foldername}/meeting_transcripts'
# # paths = mssparkutils.fs.ls(path_name)

# paths = os.listdir(path_name)

conn = psycopg2.connect(db_uri)
cur = conn.cursor()

from azure.storage.filedatalake import (
    DataLakeServiceClient,
    DataLakeDirectoryClient,
    FileSystemClient
)

file_system_client_name = "data"
directory = 'clienttranscripts/meeting_transcripts' 
csv_file_name = 'clienttranscripts/meeting_transcripts_metadata/transcripts_metadata.csv'

account_name = get_secrets_from_kv(key_vault_name, "ADLS-ACCOUNT-NAME")
account_key = get_secrets_from_kv(key_vault_name, "ADLS-ACCOUNT-KEY")

account_url = f"https://{account_name}.dfs.core.windows.net"

service_client = DataLakeServiceClient(account_url, credential=account_key,api_version='2023-01-03') 

file_system_client = service_client.get_file_system_client(file_system_client_name)  
directory_name = directory
paths = file_system_client.get_paths(path=directory_name)
# print(paths)


import pandas as pd
# Read the CSV file into a Pandas DataFrame
file_path = csv_file_name
# print(file_path)
file_client = file_system_client.get_file_client(file_path)
csv_file = file_client.download_file()
df_metadata = pd.read_csv(csv_file, encoding='utf-8')

docs = []
counter = 0
for path in paths:
    file_client = file_system_client.get_file_client(path.name)
    data_file = file_client.download_file()
    data = json.load(data_file)
    text = data['Content']

    filename = path.name.split('/')[-1]
    document_id = filename.replace('.json','').replace('convo_','')
    # print(document_id)
    df_file_metadata = df_metadata[df_metadata['ConversationId']==str(document_id)].iloc[0]
   
    chunks = chunk_data(text)
    chunk_num = 0
    for chunk in chunks:
        chunk_num += 1
        d = {
                "chunk_id" : document_id + '_' + str(chunk_num).zfill(2),
                "client_id": str(df_file_metadata['ClientId']),
                "content": 'ClientId is ' + str(df_file_metadata['ClientId']) + ' . '  + chunk,       
            }

        counter += 1

        try:
            v_contentVector = get_embeddings(d["content"],openai_api_base,openai_api_version,openai_api_key)
        except:
            time.sleep(30)
            v_contentVector = get_embeddings(d["content"],openai_api_base,openai_api_version,openai_api_key)
     

        id = base64.urlsafe_b64encode(bytes(d["chunk_id"], encoding='utf-8')).decode('utf-8')

        cur.execute(f"INSERT INTO calltranscripts (id,chunk_id, client_id, content, sourceurl, contentVector) VALUES (%s,%s,%s,%s,%s,%s)", (id, d["chunk_id"], d["client_id"], d["content"], path.name.split('/')[-1], v_contentVector))
        #break
    # break

cur.close()
conn.commit()