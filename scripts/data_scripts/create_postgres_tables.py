from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential
import psycopg2

key_vault_name = "kv_to-be-replaced"


def get_secrets_from_kv(kv_name, secret_name):
    credential = DefaultAzureCredential()
    secret_client = SecretClient(
        vault_url=f"https://{kv_name}.vault.azure.net/", credential=credential
    )  # Create a secret client object using the credential and Key Vault name
    return secret_client.get_secret(secret_name).value


host = get_secrets_from_kv(key_vault_name, "POSTGRESQL-HOST")
user = get_secrets_from_kv(key_vault_name, "POSTGRESQL-USERNAME")
dbname = get_secrets_from_kv(key_vault_name, "POSTGRESQL-DBNAME")

# Acquire the access token
cred = DefaultAzureCredential()
access_token = cred.get_token("https://ossrdbms-aad.database.windows.net/.default")

# Combine the token with the connection string to establish the connection.
conn_string = "host={0} user={1} dbname={2} password={3}".format(
    host, user, dbname, access_token.token
)
conn = psycopg2.connect(conn_string)
cursor = conn.cursor()

# Drop and recreate the conversations table
cursor.execute("DROP TABLE IF EXISTS conversations")
conn.commit()

create_cs_sql = """CREATE TABLE conversations (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    type TEXT NOT NULL,
                    "createdAt" TEXT,
                    "updatedAt" TEXT,
                    user_id TEXT NOT NULL,
                    title TEXT
                );"""
cursor.execute(create_cs_sql)
conn.commit()

# Drop and recreate the messages table
cursor.execute("DROP TABLE IF EXISTS messages")
conn.commit()

create_ms_sql = """CREATE TABLE messages (
                    id TEXT PRIMARY KEY,
                    type VARCHAR(50) NOT NULL,
                    "createdAt" TEXT,
                    "updatedAt" TEXT,
                    user_id TEXT NOT NULL,
                    conversation_id TEXT NOT NULL,
                    role VARCHAR(50),
                    content TEXT NOT NULL,
                    feedback TEXT
                );"""
cursor.execute(create_ms_sql)
conn.commit()

# Add pg_diskann extension and search_indexes table
cursor.execute("CREATE EXTENSION IF NOT EXISTS pg_diskann CASCADE;")
conn.commit()

cursor.execute("DROP TABLE IF EXISTS search_indexes;")
conn.commit()

table_create_command = """CREATE TABLE IF NOT EXISTS search_indexes(
    id text,
    title text,
    chunk integer,
    chunk_id text,
    "offset" integer,
    page_number integer,
    content text,
    source text,
    metadata text,
    content_vector vector(1536)
);"""
cursor.execute(table_create_command)
cursor.close()
conn.commit()
conn.close()
