from azure.identity import DefaultAzureCredential
import psycopg2
from pgvector.psycopg2 import register_vector


# Acquire the access token
credential = DefaultAzureCredential()
token = credential.get_token(
    "https://ossrdbms-aad.database.windows.net/.default"
).token

#TODO FIX THIS
conn_string = "host=your_postgresql_server.postgres.database.azure.com dbname=your_database "
conn = psycopg2.connect(conn_string + ' password=' + token)
cursor = conn.cursor()

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

cursor.execute("CREATE EXTENSION IF NOT EXISTS pg_diskann CASCADE;")
conn.commit()

#TODO review if this command is necessary for creating the table
# Register the vector type with psycopg2
register_vector(conn)

cursor.execute('DROP TABLE IF EXISTS search_indexes;')
# Create table to store embeddings and metadata

table_create_command = """
CREATE TABLE IF NOT EXISTS search_indexes(
            id text,
            title text,
            chunk integer,
            chunk_id text,
            offset integer,
            page_number integer,
            content text,
            source text,
            metadata text,
            content_vector vector(1536)
            );
            """

cursor.execute(table_create_command)
cursor.close()
conn.commit()