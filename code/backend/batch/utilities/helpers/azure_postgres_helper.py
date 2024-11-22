import logging
import psycopg2
from psycopg2.extras import execute_values
from azure.identity import DefaultAzureCredential
from .llm_helper import LLMHelper
from .env_helper import EnvHelper

logger = logging.getLogger(__name__)


class AzurePostgresHelper:
    def __init__(self):
        self.llm_helper = LLMHelper()
        self.env_helper = EnvHelper()
        self.conn = None

    def _create_search_client(self):
        """
        Establishes a connection to Azure PostgreSQL using AAD authentication.
        """
        try:
            user = self.env_helper.POSTGRESQL_USER
            host = self.env_helper.POSTGRESQL_HOST
            dbname = self.env_helper.POSTGRESQL_DATABASE

            # Acquire the access token
            credential = DefaultAzureCredential()
            access_token = credential.get_token(
                "https://ossrdbms-aad.database.windows.net/.default"
            )

            # Use the token in the connection string
            conn_string = (
                f"host={host} user={user} dbname={dbname} password={access_token.token}"
            )
            self.conn = psycopg2.connect(conn_string)
            logger.info("Connected to Azure PostgreSQL successfully.")
            return self.conn
        except Exception:
            logger.error("Error establishing a connection to PostgreSQL", exc_info=True)
            raise

    def get_search_client(self):
        """
        Provides a reusable database connection.
        """
        if self.conn is None or self.conn.closed != 0:  # Ensure the connection is open
            self.conn = self._create_search_client()
        return self.conn

    def get_search_indexes(self, embedding_array):
        """
        Fetches search indexes from PostgreSQL based on an embedding vector.
        """
        conn = self.get_search_client()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, title, chunk, "offset", page_number, content, source
                    FROM search_indexes
                    ORDER BY content_vector <=> %s::vector
                    LIMIT 3
                    """,
                    (embedding_array,),
                )
                search_results = cur.fetchall()
                logger.info(f"Retrieved {len(search_results)} search results.")
                return search_results
        except Exception:
            logger.error("Error executing search query", exc_info=True)
            raise
        finally:
            conn.close()

    def create_search_indexes(self, documents_to_upload):
        """
        Inserts documents into the `search_indexes` table in batch mode.
        """
        conn = self.get_search_client()
        try:
            with conn.cursor() as cur:
                data_to_insert = [
                    (
                        d["id"],
                        d["title"],
                        d["chunk"],
                        d["chunk_id"],
                        d["offset"],
                        d["page_number"],
                        d["content"],
                        d["source"],
                        d["metadata"],
                        d["content_vector"],
                    )
                    for d in documents_to_upload
                ]

                # Batch insert using execute_values for efficiency
                query = """
                    INSERT INTO search_indexes (
                        id, title, chunk, chunk_id, "offset", page_number,
                        content, source, metadata, content_vector
                    ) VALUES %s
                """
                execute_values(cur, query, data_to_insert)
                logger.info(
                    f"Inserted {len(documents_to_upload)} documents successfully."
                )

            conn.commit()  # Commit the transaction
        except Exception:
            logger.error("Error during index creation", exc_info=True)
            conn.rollback()  # Roll back transaction on error
            raise
        finally:
            conn.close()
