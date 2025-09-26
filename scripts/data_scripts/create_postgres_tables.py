from azure_credential_utils import get_azure_credential
import psycopg2
from psycopg2 import sql
import requests

principalId = "userPrincipalId"
user = "managedIdentityName"
host = "serverName"
dbname = "postgres"


def get_user_principal_name(principal_id, credential):
    """
    Get user principal name (UPN/email) from a principal ID using Microsoft Graph API.

    Parameters:
    - principal_id: The Azure AD object ID of the user or service principal
    - credential: Azure credential object for authentication

    Returns:
    - UPN/email of the user or the principal_id if not found
    """
    try:
        # Get access token for Microsoft Graph
        token = credential.get_token("https://graph.microsoft.com/.default")

        headers = {
            "Authorization": f"Bearer {token.token}",
            "Content-Type": "application/json"
        }

        # Try to get user details
        user_url = f"https://graph.microsoft.com/v1.0/users/{principal_id}"
        response = requests.get(user_url, headers=headers, timeout=30)

        if response.status_code == 200:
            user_data = response.json()
            # Return userPrincipalName if available, otherwise return mail
            return user_data.get("userPrincipalName", user_data.get("mail", principal_id))

        # If not found as user, try as service principal
        sp_url = f"https://graph.microsoft.com/v1.0/servicePrincipals/{principal_id}"
        response = requests.get(sp_url, headers=headers, timeout=30)

        if response.status_code == 200:
            sp_data = response.json()
            # For service principals, use appId or displayName as identifier
            return sp_data.get("displayName", principal_id)

        # If neither found, return the ID itself
        print(f"Could not find UPN for principal ID {principal_id}. Using ID as fallback.")
        return principal_id

    except Exception as e:
        print(f"Error retrieving UPN: {str(e)}")
        return principal_id


def grant_permissions(cursor, dbname, schema_name, principal_id):
    """
    Grants database and schema-level permissions to a specified principal.

    Parameters:
    - cursor: psycopg2 cursor object for database operations.
    - dbname: Name of the database to grant CONNECT permission.
    - schema_name: Name of the schema to grant table-level permissions.
    - principal_id: ID of the principal (role or user) to grant permissions.
    """

    # Check if the principal exists in the database
    cursor.execute(
        sql.SQL("SELECT 1 FROM pg_roles WHERE rolname = {principal}").format(
            principal=sql.Literal(principal_id)
        )
    )
    if cursor.fetchone() is None:
        add_principal_user_query = sql.SQL(
            "SELECT * FROM pgaadauth_create_principal({principal}, false, false)"
        )
        cursor.execute(
            add_principal_user_query.format(
                principal=sql.Literal(principal_id),
            )
        )

    # Grant CONNECT on database
    grant_connect_query = sql.SQL("GRANT CONNECT ON DATABASE {database} TO {principal}")
    cursor.execute(
        grant_connect_query.format(
            database=sql.Identifier(dbname),
            principal=sql.Identifier(principal_id),
        )
    )
    print(f"Granted CONNECT on database '{dbname}' to '{principal_id}'")

    # Grant SELECT, INSERT, UPDATE, DELETE on schema tables
    grant_permissions_query = sql.SQL(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA {schema} TO {principal}"
    )
    cursor.execute(
        grant_permissions_query.format(
            schema=sql.Identifier(schema_name),
            principal=sql.Identifier(principal_id),
        )
    )


# Acquire the access token
cred = get_azure_credential()
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

if principalId and principalId.strip():
    identifier_to_use = get_user_principal_name(principalId, cred)
    grant_permissions(cursor, dbname, "public", identifier_to_use)
    conn.commit()

cursor.execute("ALTER TABLE public.conversations OWNER TO azure_pg_admin;")
cursor.execute("ALTER TABLE public.messages OWNER TO azure_pg_admin;")
cursor.execute("ALTER TABLE public.vector_store OWNER TO azure_pg_admin;")
conn.commit()

cursor.close()
conn.close()
