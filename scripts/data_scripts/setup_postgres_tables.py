"""Creates PostgreSQL tables for chat history and vector storage.

Usage:
    python setup_postgres_tables.py <server_fqdn> <user>

Authentication:
    The script authenticates to PostgreSQL using a Microsoft Entra ID access
    token (the ``ossrdbms-aad`` resource). It resolves the token in this order:

    1. ``PG_ACCESS_TOKEN`` environment variable, if set. The post-deployment
       wrapper scripts (``post_deployment_setup.sh`` / ``.ps1``) acquire the
       token via ``az account get-access-token`` immediately before invoking
       this script and export it as ``PG_ACCESS_TOKEN`` to avoid token expiry
       (especially for federated service principals where ``DefaultAzureCredential``
       may fail).
    2. Fallback: ``azure.identity.DefaultAzureCredential`` is used to acquire
       a token in-process when ``PG_ACCESS_TOKEN`` is not set.
"""

import os
import sys
import psycopg2

if len(sys.argv) != 3:
    print("Usage: python setup_postgres_tables.py <server_fqdn> <user>")
    sys.exit(1)

host = sys.argv[1]
user = sys.argv[2]
dbname = "postgres"

token = os.environ.get("PG_ACCESS_TOKEN")
if not token:
    from azure.identity import DefaultAzureCredential

    cred = DefaultAzureCredential()
    token = cred.get_token(
        "https://ossrdbms-aad.database.windows.net/.default"
    ).token

conn = psycopg2.connect(
    host=host,
    user=user,
    dbname=dbname,
    password=token,
    sslmode="require",
)
cursor = conn.cursor()

# Drop and recreate the conversations table
cursor.execute("DROP TABLE IF EXISTS conversations")
conn.commit()

cursor.execute(
    """CREATE TABLE conversations (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    type TEXT NOT NULL,
    "createdAt" TEXT,
    "updatedAt" TEXT,
    user_id TEXT NOT NULL,
    title TEXT
);"""
)
conn.commit()

# Drop and recreate the messages table
cursor.execute("DROP TABLE IF EXISTS messages")
conn.commit()

cursor.execute(
    """CREATE TABLE messages (
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
)
conn.commit()

# Add Vector extension
cursor.execute("CREATE EXTENSION IF NOT EXISTS vector CASCADE;")
conn.commit()

cursor.execute("DROP TABLE IF EXISTS vector_store;")
conn.commit()

cursor.execute(
    """CREATE TABLE IF NOT EXISTS vector_store(
    id text,
    title text,
    chunk integer,
    chunk_id text,
    "offset" integer,
    page_number integer,
    content text,
    source text,
    metadata text,
    content_vector public.vector(1536)
);"""
)
conn.commit()

cursor.execute(
    "CREATE INDEX vector_store_content_vector_idx ON vector_store USING hnsw (content_vector vector_cosine_ops);"
)
conn.commit()

cursor.execute("ALTER TABLE public.conversations OWNER TO azure_pg_admin;")
cursor.execute("ALTER TABLE public.messages OWNER TO azure_pg_admin;")
cursor.execute("ALTER TABLE public.vector_store OWNER TO azure_pg_admin;")
conn.commit()

cursor.close()
conn.close()
print("PostgreSQL tables created successfully.")
