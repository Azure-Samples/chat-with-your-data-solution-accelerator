from azure.identity import DefaultAzureCredential
import psycopg2
from psycopg2 import sql

key_vault_name = "kv_to-be-replaced"
principal_name = "webAppPrincipalName"
admin_principal_name = "adminAppPrincipalName"
function_app_principal_name = "functionAppPrincipalName"
user = "managedIdentityName"
host = "serverName"
dbname = "postgres"


def grant_permissions(cursor, dbname, schema_name, principal_name):
    """
    Grants database and schema-level permissions to a specified principal.

    Parameters:
    - cursor: psycopg2 cursor object for database operations.
    - dbname: Name of the database to grant CONNECT permission.
    - schema_name: Name of the schema to grant table-level permissions.
    - principal_name: Name of the principal (role or user) to grant permissions.
    """

    # Check if the principal exists in the database
    cursor.execute(
        sql.SQL("SELECT 1 FROM pg_roles WHERE rolname = {principal}").format(
            principal=sql.Literal(principal_name)
        )
    )
    if cursor.fetchone() is None:
        add_principal_user_query = sql.SQL(
            "SELECT * FROM pgaadauth_create_principal({principal}, false, false)"
        )
        cursor.execute(
            add_principal_user_query.format(
                principal=sql.Literal(principal_name),
            )
        )

    # Grant CONNECT on database
    grant_connect_query = sql.SQL("GRANT CONNECT ON DATABASE {database} TO {principal}")
    cursor.execute(
        grant_connect_query.format(
            database=sql.Identifier(dbname),
            principal=sql.Identifier(principal_name),
        )
    )
    print(f"Granted CONNECT on database '{dbname}' to '{principal_name}'")

    # Grant SELECT, INSERT, UPDATE, DELETE on schema tables
    grant_permissions_query = sql.SQL(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA {schema} TO {principal}"
    )
    cursor.execute(
        grant_permissions_query.format(
            schema=sql.Identifier(schema_name),
            principal=sql.Identifier(principal_name),
        )
    )


# Acquire the access token
cred = DefaultAzureCredential()
access_token = cred.get_token("https://ossrdbms-aad.database.windows.net/.default")

# Combine the token with the connection string to establish the connection.
conn_string = "host={0} user={1} dbname={2} password={3} sslmode=require".format(
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

grant_permissions(cursor, dbname, "public", principal_name)
conn.commit()

grant_permissions(cursor, dbname, "public", admin_principal_name)
conn.commit()

grant_permissions(cursor, dbname, "public", function_app_principal_name)
conn.commit()

cursor.execute("ALTER TABLE public.conversations OWNER TO azure_pg_admin;")
cursor.execute("ALTER TABLE public.messages OWNER TO azure_pg_admin;")
cursor.execute("ALTER TABLE public.vector_store OWNER TO azure_pg_admin;")
conn.commit()

cursor.close()
conn.close()
