from azure.identity import DefaultAzureCredential
import psycopg2
from pgvector.psycopg2 import register_vector
from openai import AzureOpenAI
import time


class PostgresSearchClient:

    def __init__(self, user: str, host: str, database: str):
        self.user = user
        self.host = host
        self.database = database
        self.conn = None

    async def connect(self):
        """
        Create a new database connection.

        The connection parameters can be specified as a string:

            conn = psycopg2.connect("dbname=test user=postgres password=secret")

        or using a set of keyword arguments:

            conn = psycopg2.connect(database="test", user="postgres", password="secret")

        Or as a mix of both. The basic connection parameters are:

        - *dbname*: the database name
        - *database*: the database name (only as keyword argument)
        - *user*: user name used to authenticate
        - *password*: password used to authenticate
        - *host*: database host address (defaults to UNIX socket if not provided)
        - *port*: connection port number (defaults to 5432 if not provided)
        """
        credential = DefaultAzureCredential()
        token = credential.get_token(
            "https://ossrdbms-aad.database.windows.net/.default"
        ).token
        # TODO FIX THIS
        conn_string = "host=your_postgresql_server.postgres.database.azure.com dbname=your_database "
        self.conn = psycopg2.connect(conn_string + " passwor=" + token)

    async def get_embeddings(
        self, text: str, openai_api_base, openai_api_version, openai_api_key
    ):
        model_id = "text-embedding-ada-002"
        client = AzureOpenAI(
            api_version=openai_api_version,
            azure_endpoint=openai_api_base,
            api_key=openai_api_key,
        )

        embedding = (
            client.embeddings.create(input=text, model=model_id).data[0].embedding
        )
        return embedding

    async def create_vector(self):
        try:
            v_contentVector = self.get_embeddings(
                d["content"], openai_api_base, openai_api_version, openai_api_key
            )
        except:
            time.sleep(30)
            v_contentVector = self.get_embeddings(
                d["content"], openai_api_base, openai_api_version, openai_api_key
            )
        return v_contentVector

    async def insert_vector(self):
        # TODO FIX THIS
        self.connect()
        cur = self.conn.cursor()
        cur.execute(
            f"INSERT INTO search_index (id,chunk_id, client_id, content, sourceurl, contentVector) VALUES (%s,%s,%s,%s,%s,%s)",
            (
                id,
                d["chunk_id"],
                d["client_id"],
                d["content"],
                path.name.split("/")[-1],
                v_contentVector,
            ),
        )
        cur.close()
        self.conn.commit()
