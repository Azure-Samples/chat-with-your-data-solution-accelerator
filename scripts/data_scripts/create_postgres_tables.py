from azure_credential_utils import get_azure_credential
import psycopg2
from psycopg2 import sql

principalId = "userPrincipalId"
user = "managedIdentityName"
host = "serverName"
dbname = "postgres"


# Acquire the access token
cred = get_azure_credential()
access_token = cred.get_token("https://ossrdbms-aad.database.windows.net/.default")

# Combine the token with the connection string to establish the connection.
conn_string = "host={0} user={1} dbname={2} password={3} sslmode=require".format(
    host, user, dbname, access_token.token
)
conn = psycopg2.connect(conn_string)
cursor = conn.cursor()

# Grant admin privileges to the principal
cursor.execute(
    sql.SQL("ALTER ROLE {} WITH SUPERUSER").format(
        sql.Identifier(principalId)
    )
)
conn.commit()

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


# Add Vector extension
cursor.execute("CREATE EXTENSION IF NOT EXISTS vector CASCADE;")
conn.commit()

cursor.execute("DROP TABLE IF EXISTS vector_store;")
conn.commit()

table_create_command = """CREATE TABLE IF NOT EXISTS vector_store(
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

cursor.execute(table_create_command)
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
