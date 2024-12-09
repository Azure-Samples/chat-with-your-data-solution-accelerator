import logging
import psycopg2
from psycopg2.extras import execute_values, RealDictCursor
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
        except Exception as e:
            logger.error(f"Error establishing a connection to PostgreSQL: {e}")
            raise

    def get_search_client(self):
        """
        Provides a reusable database connection.
        """
        if self.conn is None or self.conn.closed != 0:  # Ensure the connection is open
            self.conn = self._create_search_client()
        return self.conn

    def get_vector_store(self, embedding_array):
        """
        Fetches search indexes from PostgreSQL based on an embedding vector.
        """
        conn = self.get_search_client()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT id, title, chunk, "offset", page_number, content, source
                    FROM vector_store
                    ORDER BY content_vector <=> %s::vector
                    LIMIT %s
                    """,
                    (
                        embedding_array,
                        self.env_helper.AZURE_POSTGRES_SEARCH_TOP_K,
                    ),
                )
                search_results = cur.fetchall()
                logger.info(f"Retrieved {len(search_results)} search results.")
                return search_results
        except Exception as e:
            logger.error(f"Error executing search query: {e}")
            raise
        finally:
            conn.close()

    def create_vector_store(self, documents_to_upload):
        """
        Inserts documents into the `vector_store` table in batch mode.
        """
        conn = self.get_search_client()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
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
                    INSERT INTO vector_store (
                        id, title, chunk, chunk_id, "offset", page_number,
                        content, source, metadata, content_vector
                    ) VALUES %s
                """
                execute_values(cur, query, data_to_insert)
                logger.info(
                    f"Inserted {len(documents_to_upload)} documents successfully."
                )

            conn.commit()  # Commit the transaction
        except Exception as e:
            logger.error(f"Error during index creation: {e}")
            conn.rollback()  # Roll back transaction on error
            raise
        finally:
            conn.close()

    def get_files(self):
        """
        Fetches distinct titles from the PostgreSQL database.

        Returns:
            list[dict] or None: A list of dictionaries (each with a single key 'title')
            or None if no titles are found or an error occurs.
        """
        conn = self.get_search_client()
        try:
            # Using a cursor to execute the query
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                query = """
                    SELECT id, title
                    FROM vector_store
                    WHERE title IS NOT NULL
                    ORDER BY title;
                """
                cursor.execute(query)
                # Fetch all results
                results = cursor.fetchall()
                # Return results or None if empty
                return results if results else None
        except psycopg2.Error as db_err:
            logger.error(f"Database error while fetching titles: {db_err}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error while fetching titles: {e}")
            raise
        finally:
            conn.close()

    def delete_documents(self, ids_to_delete):
        """
        Deletes documents from the PostgreSQL database based on the provided ids.

        Args:
            ids_to_delete (list): A list of document IDs to delete.

        Returns:
            int: The number of deleted rows.
        """
        conn = self.get_search_client()
        try:
            if not ids_to_delete:
                logger.warning("No IDs provided for deletion.")
                return 0

            # Using a cursor to execute the query
            with conn.cursor() as cursor:
                # Construct the DELETE query with the list of ids_to_delete
                query = """
                    DELETE FROM vector_store
                    WHERE id = ANY(%s)
                """
                # Extract the 'id' values from the list of dictionaries (ids_to_delete)
                ids_to_delete_values = [item["id"] for item in ids_to_delete]

                # Execute the query, passing the list of IDs as a parameter
                cursor.execute(query, (ids_to_delete_values,))

                # Commit the transaction
                conn.commit()

                # Return the number of deleted rows
                deleted_rows = cursor.rowcount
                logger.info(f"Deleted {deleted_rows} documents.")
                return deleted_rows
        except psycopg2.Error as db_err:
            logger.error(f"Database error while deleting documents: {db_err}")
            conn.rollback()
            raise
        except Exception as e:
            logger.error(f"Unexpected error while deleting documents: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

    def perform_search(self, title):
        """
        Fetches search results from PostgreSQL based on the title.
        """
        # Establish connection to PostgreSQL
        conn = self.get_search_client()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Execute query to fetch title, content, and metadata
                cur.execute(
                    """
                    SELECT title, content, metadata
                    FROM vector_store
                    WHERE title = %s
                    """,
                    (title,),
                )
                results = cur.fetchall()  # Fetch all matching results
                logger.info(f"Retrieved {len(results)} search result(s).")
                return results
        except Exception as e:
            logger.error(f"Error executing search query: {e}")
            raise
        finally:
            conn.close()

    def get_unique_files(self):
        """
        Fetches unique titles from PostgreSQL.
        """
        # Establish connection to PostgreSQL
        conn = self.get_search_client()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Execute query to fetch distinct titles
                cur.execute(
                    """
                    SELECT DISTINCT title
                    FROM vector_store
                    """
                )
                results = cur.fetchall()  # Fetch all results as RealDictRow objects
                logger.info(f"Retrieved {len(results)} unique title(s).")
                return results
        except Exception as e:
            logger.error(f"Error executing search query: {e}")
            raise
        finally:
            conn.close()

    def search_by_blob_url(self, blob_url):
        """
        Fetches unique titles from PostgreSQL based on a given blob URL.
        """
        # Establish connection to PostgreSQL
        conn = self.get_search_client()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Execute parameterized query to fetch results
                cur.execute(
                    """
                    SELECT id, title
                    FROM vector_store
                    WHERE source = %s
                    """,
                    (f"{blob_url}_SAS_TOKEN_PLACEHOLDER_",),
                )
                results = cur.fetchall()  # Fetch all results as RealDictRow objects
                logger.info(f"Retrieved {len(results)} unique title(s).")
                return results
        except Exception as e:
            logger.error(f"Error executing search query: {e}")
            raise
        finally:
            conn.close()
