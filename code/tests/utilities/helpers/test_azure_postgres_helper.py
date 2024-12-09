import unittest
from unittest.mock import MagicMock, patch
import psycopg2
from backend.batch.utilities.helpers.azure_postgres_helper import AzurePostgresHelper


class TestAzurePostgresHelper(unittest.TestCase):
    @patch(
        "backend.batch.utilities.helpers.azure_postgres_helper.DefaultAzureCredential"
    )
    @patch("backend.batch.utilities.helpers.azure_postgres_helper.psycopg2.connect")
    def test_create_search_client_success(self, mock_connect, mock_credential):
        # Arrange
        mock_access_token = MagicMock()
        mock_access_token.token = "mock-access-token"
        mock_credential.return_value.get_token.return_value = mock_access_token

        mock_connection = MagicMock()
        mock_connect.return_value = mock_connection

        helper = AzurePostgresHelper()
        helper.env_helper.POSTGRESQL_USER = "mock_user"
        helper.env_helper.POSTGRESQL_HOST = "mock_host"
        helper.env_helper.POSTGRESQL_DATABASE = "mock_database"

        # Act
        connection = helper._create_search_client()

        # Assert
        self.assertEqual(connection, mock_connection)
        mock_credential.return_value.get_token.assert_called_once_with(
            "https://ossrdbms-aad.database.windows.net/.default"
        )
        mock_connect.assert_called_once_with(
            "host=mock_host user=mock_user dbname=mock_database password=mock-access-token"
        )

    @patch("backend.batch.utilities.helpers.azure_postgres_helper.psycopg2.connect")
    def test_get_search_client_reuses_connection(self, mock_connect):
        # Arrange
        mock_connection = MagicMock()
        mock_connection.closed = 0  # Simulate an open connection
        mock_connect.return_value = mock_connection

        helper = AzurePostgresHelper()
        helper.conn = mock_connection

        # Act
        connection = helper.get_search_client()

        # Assert
        self.assertEqual(connection, mock_connection)
        mock_connect.assert_not_called()  # Ensure no new connection is created

    @patch(
        "backend.batch.utilities.helpers.azure_postgres_helper.DefaultAzureCredential"
    )
    @patch("backend.batch.utilities.helpers.azure_postgres_helper.psycopg2.connect")
    @patch("backend.batch.utilities.helpers.azure_postgres_helper.RealDictCursor")
    def test_get_vector_store_success(
        self, mock_cursor, mock_connect, mock_credential
    ):
        # Arrange
        # Mock the EnvHelper and set required attributes
        mock_env_helper = MagicMock()
        mock_env_helper.POSTGRESQL_USER = "mock_user"
        mock_env_helper.POSTGRESQL_HOST = "mock_host"
        mock_env_helper.POSTGRESQL_DATABASE = "mock_database"
        mock_env_helper.AZURE_POSTGRES_SEARCH_TOP_K = 5

        # Mock access token retrieval
        mock_access_token = MagicMock()
        mock_access_token.token = "mock-access-token"
        mock_credential.return_value.get_token.return_value = mock_access_token

        # Mock the database connection and cursor
        mock_connection = MagicMock()
        mock_connect.return_value = mock_connection
        mock_cursor_instance = MagicMock()
        mock_cursor.return_value = mock_cursor_instance

        # Mock the behavior of the context manager for the cursor
        mock_cursor_context = MagicMock()
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor_context
        mock_results = [{"id": 1, "title": "Test"}]
        mock_cursor_context.fetchall.return_value = mock_results

        # Replace EnvHelper in AzurePostgresHelper with the mocked version
        helper = AzurePostgresHelper()
        helper.env_helper = mock_env_helper

        # Embedding vector for the test
        embedding_vector = [1, 2, 3]

        # Act
        results = helper.get_vector_store(embedding_vector)

        # Assert
        self.assertEqual(results, mock_results)
        mock_connect.assert_called_once_with(
            "host=mock_host user=mock_user dbname=mock_database password=mock-access-token"
        )

    @patch(
        "backend.batch.utilities.helpers.azure_postgres_helper.DefaultAzureCredential"
    )
    @patch("backend.batch.utilities.helpers.azure_postgres_helper.psycopg2.connect")
    def test_get_vector_store_query_error(self, mock_connect, mock_credential):
        # Arrange
        # Mock the EnvHelper and set required attributes
        mock_env_helper = MagicMock()
        mock_env_helper.POSTGRESQL_USER = "mock_user"
        mock_env_helper.POSTGRESQL_HOST = "mock_host"
        mock_env_helper.POSTGRESQL_DATABASE = "mock_database"
        mock_env_helper.AZURE_POSTGRES_SEARCH_TOP_K = 5

        # Mock access token retrieval
        mock_access_token = MagicMock()
        mock_access_token.token = "mock-access-token"
        mock_credential.return_value.get_token.return_value = mock_access_token

        mock_connection = MagicMock()
        mock_connect.return_value = mock_connection

        def raise_exception(*args, **kwargs):
            raise Exception("Query execution error")

        mock_cursor_instance = MagicMock()
        mock_cursor_instance.execute.side_effect = raise_exception

        mock_connection.cursor.return_value.__enter__.return_value = (
            mock_cursor_instance
        )

        helper = AzurePostgresHelper()
        helper.env_helper = mock_env_helper
        embedding_vector = [1, 2, 3]

        # Act & Assert
        with self.assertRaises(Exception) as context:
            helper.get_vector_store(embedding_vector)

        self.assertEqual(str(context.exception), "Query execution error")

    @patch(
        "backend.batch.utilities.helpers.azure_postgres_helper.DefaultAzureCredential"
    )
    @patch("backend.batch.utilities.helpers.azure_postgres_helper.psycopg2.connect")
    def test_create_search_client_connection_error(self, mock_connect, mock_credential):
        # Arrange
        # Mock the EnvHelper and set required attributes
        mock_env_helper = MagicMock()
        mock_env_helper.POSTGRESQL_USER = "mock_user"
        mock_env_helper.POSTGRESQL_HOST = "mock_host"
        mock_env_helper.POSTGRESQL_DATABASE = "mock_database"
        mock_env_helper.AZURE_POSTGRES_SEARCH_TOP_K = 5

        # Mock access token retrieval
        mock_access_token = MagicMock()
        mock_access_token.token = "mock-access-token"
        mock_credential.return_value.get_token.return_value = mock_access_token

        def raise_exception(*args, **kwargs):
            raise Exception("Connection error")

        mock_connect.side_effect = raise_exception

        helper = AzurePostgresHelper()
        helper.env_helper = mock_env_helper

        # Act & Assert
        with self.assertRaises(Exception) as context:
            helper._create_search_client()

        self.assertEqual(str(context.exception), "Connection error")

    @patch(
        "backend.batch.utilities.helpers.azure_postgres_helper.DefaultAzureCredential"
    )
    @patch("backend.batch.utilities.helpers.azure_postgres_helper.psycopg2.connect")
    @patch("backend.batch.utilities.helpers.azure_postgres_helper.EnvHelper")
    def test_get_files_success(self, mock_env_helper, mock_connect, mock_credential):
        # Mock the EnvHelper attributes
        mock_env_helper.POSTGRESQL_USER = "mock_user"
        mock_env_helper.POSTGRESQL_HOST = "mock_host"
        mock_env_helper.POSTGRESQL_DATABASE = "mock_database"
        mock_env_helper.AZURE_POSTGRES_SEARCH_TOP_K = 5

        # Mock access token retrieval
        mock_access_token = MagicMock()
        mock_access_token.token = "mock-access-token"
        mock_credential.return_value.get_token.return_value = mock_access_token

        # Arrange: Mock the connection and cursor
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value = mock_connection

        # Mock the result of the cursor's fetchall() method
        mock_cursor.fetchall.return_value = [
            {"id": 1, "title": "Title 1"},
            {"id": 2, "title": "Title 2"},
        ]

        # Create an instance of the helper
        helper = AzurePostgresHelper()

        # Act: Call the method under test
        result = helper.get_files()

        # Assert: Check that the correct results are returned
        self.assertEqual(
            result, [{"id": 1, "title": "Title 1"}, {"id": 2, "title": "Title 2"}]
        )
        mock_connection.close.assert_called_once()

    @patch(
        "backend.batch.utilities.helpers.azure_postgres_helper.DefaultAzureCredential"
    )
    @patch("backend.batch.utilities.helpers.azure_postgres_helper.psycopg2.connect")
    @patch("backend.batch.utilities.helpers.azure_postgres_helper.EnvHelper")
    def test_get_files_no_results(self, mock_env_helper, mock_connect, mock_credential):
        # Mock the EnvHelper attributes
        mock_env_helper.POSTGRESQL_USER = "mock_user"
        mock_env_helper.POSTGRESQL_HOST = "mock_host"
        mock_env_helper.POSTGRESQL_DATABASE = "mock_database"
        mock_env_helper.AZURE_POSTGRES_SEARCH_TOP_K = 5

        # Mock access token retrieval
        mock_access_token = MagicMock()
        mock_access_token.token = "mock-access-token"
        mock_credential.return_value.get_token.return_value = mock_access_token

        # Arrange: Mock the connection and cursor
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value = mock_connection

        # Mock the result of the cursor's fetchall() method to return an empty list
        mock_cursor.fetchall.return_value = []

        # Create an instance of the helper
        helper = AzurePostgresHelper()

        # Act: Call the method under test
        result = helper.get_files()

        # Assert: Check that the result is None
        self.assertIsNone(result)
        mock_connection.close.assert_called_once()

    @patch(
        "backend.batch.utilities.helpers.azure_postgres_helper.DefaultAzureCredential"
    )
    @patch("backend.batch.utilities.helpers.azure_postgres_helper.psycopg2.connect")
    @patch("backend.batch.utilities.helpers.azure_postgres_helper.EnvHelper")
    @patch("backend.batch.utilities.helpers.azure_postgres_helper.logger")
    def test_get_files_db_error(
        self, mock_logger, mock_env_helper, mock_connect, mock_credential
    ):
        # Mock the EnvHelper attributes
        mock_env_helper.POSTGRESQL_USER = "mock_user"
        mock_env_helper.POSTGRESQL_HOST = "mock_host"
        mock_env_helper.POSTGRESQL_DATABASE = "mock_database"
        mock_env_helper.AZURE_POSTGRES_SEARCH_TOP_K = 5

        # Mock access token retrieval
        mock_access_token = MagicMock()
        mock_access_token.token = "mock-access-token"
        mock_credential.return_value.get_token.return_value = mock_access_token

        # Arrange: Mock the connection and cursor
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value = mock_connection

        # Simulate a database error when executing the query
        mock_cursor.fetchall.side_effect = psycopg2.Error("Database error")

        # Create an instance of the helper
        helper = AzurePostgresHelper()

        # Act & Assert: Ensure that the exception is raised and the error is logged
        with self.assertRaises(psycopg2.Error):
            helper.get_files()

        mock_logger.error.assert_called_with(
            "Database error while fetching titles: Database error"
        )
        mock_connection.close.assert_called_once()

    @patch(
        "backend.batch.utilities.helpers.azure_postgres_helper.DefaultAzureCredential"
    )
    @patch("backend.batch.utilities.helpers.azure_postgres_helper.psycopg2.connect")
    @patch("backend.batch.utilities.helpers.azure_postgres_helper.EnvHelper")
    @patch("backend.batch.utilities.helpers.azure_postgres_helper.logger")
    def test_get_files_unexpected_error(
        self, mock_logger, mock_env_helper, mock_connect, mock_credential
    ):
        # Mock the EnvHelper attributes
        mock_env_helper.POSTGRESQL_USER = "mock_user"
        mock_env_helper.POSTGRESQL_HOST = "mock_host"
        mock_env_helper.POSTGRESQL_DATABASE = "mock_database"
        mock_env_helper.AZURE_POSTGRES_SEARCH_TOP_K = 5

        # Mock access token retrieval
        mock_access_token = MagicMock()
        mock_access_token.token = "mock-access-token"
        mock_credential.return_value.get_token.return_value = mock_access_token

        # Arrange: Mock the connection and cursor
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value = mock_connection

        # Simulate an unexpected error
        mock_cursor.fetchall.side_effect = Exception("Unexpected error")

        # Create an instance of the helper
        helper = AzurePostgresHelper()

        # Act & Assert: Ensure that the exception is raised and the error is logged
        with self.assertRaises(Exception):
            helper.get_files()

        mock_logger.error.assert_called_with(
            "Unexpected error while fetching titles: Unexpected error"
        )
        mock_connection.close.assert_called_once()

    @patch(
        "backend.batch.utilities.helpers.azure_postgres_helper.DefaultAzureCredential"
    )
    @patch("backend.batch.utilities.helpers.azure_postgres_helper.psycopg2.connect")
    @patch("backend.batch.utilities.helpers.azure_postgres_helper.logger")
    @patch("backend.batch.utilities.helpers.azure_postgres_helper.EnvHelper")
    def test_delete_documents_success(
        self, mock_env_helper, mock_logger, mock_connect, mock_credential
    ):
        # Arrange: Mock the EnvHelper attributes
        mock_env_helper.POSTGRESQL_USER = "mock_user"
        mock_env_helper.POSTGRESQL_HOST = "mock_host"
        mock_env_helper.POSTGRESQL_DATABASE = "mock_database"
        mock_env_helper.AZURE_POSTGRES_SEARCH_TOP_K = 5

        # Mock access token retrieval
        mock_access_token = MagicMock()
        mock_access_token.token = "mock-access-token"
        mock_credential.return_value.get_token.return_value = mock_access_token

        # Mock the connection and cursor
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value = mock_connection

        # Mock the behavior of cursor.rowcount and execute
        mock_cursor.rowcount = 3  # Simulate 3 rows deleted
        mock_cursor.execute.return_value = None

        ids_to_delete = [{"id": 1}, {"id": 2}, {"id": 3}]

        # Create an instance of the helper
        helper = AzurePostgresHelper()

        # Act: Call the method under test
        result = helper.delete_documents(ids_to_delete)

        # Assert: Check that the correct number of rows were deleted
        self.assertEqual(result, 3)
        mock_connection.commit.assert_called_once()
        mock_connection.close.assert_called_once()
        mock_logger.info.assert_called_with("Deleted 3 documents.")

    @patch(
        "backend.batch.utilities.helpers.azure_postgres_helper.DefaultAzureCredential"
    )
    @patch("backend.batch.utilities.helpers.azure_postgres_helper.psycopg2.connect")
    @patch("backend.batch.utilities.helpers.azure_postgres_helper.logger")
    @patch("backend.batch.utilities.helpers.azure_postgres_helper.EnvHelper")
    def test_delete_documents_no_ids(
        self, mock_env_helper, mock_logger, mock_connect, mock_credential
    ):
        # Arrange: Mock the EnvHelper attributes
        mock_env_helper.POSTGRESQL_USER = "mock_user"
        mock_env_helper.POSTGRESQL_HOST = "mock_host"
        mock_env_helper.POSTGRESQL_DATABASE = "mock_database"
        mock_env_helper.AZURE_POSTGRES_SEARCH_TOP_K = 5

        # Mock access token retrieval
        mock_access_token = MagicMock()
        mock_access_token.token = "mock-access-token"
        mock_credential.return_value.get_token.return_value = mock_access_token

        # Mock the connection and cursor
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value = mock_connection

        # No IDs to delete
        ids_to_delete = []

        # Create an instance of the helper
        helper = AzurePostgresHelper()

        # Act: Call the method under test
        result = helper.delete_documents(ids_to_delete)

        # Assert: Check that no rows were deleted and a warning was logged
        self.assertEqual(result, 0)
        mock_logger.warning.assert_called_with("No IDs provided for deletion.")
        mock_connection.close.assert_called_once()

    @patch(
        "backend.batch.utilities.helpers.azure_postgres_helper.DefaultAzureCredential"
    )
    @patch("backend.batch.utilities.helpers.azure_postgres_helper.psycopg2.connect")
    @patch("backend.batch.utilities.helpers.azure_postgres_helper.logger")
    @patch("backend.batch.utilities.helpers.azure_postgres_helper.EnvHelper")
    def test_delete_documents_db_error(
        self, mock_env_helper, mock_logger, mock_connect, mock_credential
    ):
        # Arrange: Mock the EnvHelper attributes
        mock_env_helper.POSTGRESQL_USER = "mock_user"
        mock_env_helper.POSTGRESQL_HOST = "mock_host"
        mock_env_helper.POSTGRESQL_DATABASE = "mock_database"
        mock_env_helper.AZURE_POSTGRES_SEARCH_TOP_K = 5

        # Mock access token retrieval
        mock_access_token = MagicMock()
        mock_access_token.token = "mock-access-token"
        mock_credential.return_value.get_token.return_value = mock_access_token

        # Mock the connection and cursor
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value = mock_connection

        # Simulate a database error during execution
        mock_cursor.execute.side_effect = psycopg2.Error("Database error")

        ids_to_delete = [{"id": 1}, {"id": 2}]

        # Create an instance of the helper
        helper = AzurePostgresHelper()

        # Act & Assert: Ensure that the exception is raised and the error is logged
        with self.assertRaises(psycopg2.Error):
            helper.delete_documents(ids_to_delete)

        mock_logger.error.assert_called_with(
            "Database error while deleting documents: Database error"
        )
        mock_connection.rollback.assert_called_once()
        mock_connection.close.assert_called_once()

    @patch(
        "backend.batch.utilities.helpers.azure_postgres_helper.DefaultAzureCredential"
    )
    @patch("backend.batch.utilities.helpers.azure_postgres_helper.psycopg2.connect")
    @patch("backend.batch.utilities.helpers.azure_postgres_helper.logger")
    @patch("backend.batch.utilities.helpers.azure_postgres_helper.EnvHelper")
    def test_delete_documents_unexpected_error(
        self, mock_env_helper, mock_logger, mock_connect, mock_credential
    ):
        # Arrange: Mock the EnvHelper attributes
        mock_env_helper.POSTGRESQL_USER = "mock_user"
        mock_env_helper.POSTGRESQL_HOST = "mock_host"
        mock_env_helper.POSTGRESQL_DATABASE = "mock_database"
        mock_env_helper.AZURE_POSTGRES_SEARCH_TOP_K = 5

        # Mock access token retrieval
        mock_access_token = MagicMock()
        mock_access_token.token = "mock-access-token"
        mock_credential.return_value.get_token.return_value = mock_access_token

        # Mock the connection and cursor
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value = mock_connection

        # Simulate an unexpected error
        mock_cursor.execute.side_effect = Exception("Unexpected error")

        ids_to_delete = [{"id": 1}, {"id": 2}]

        # Create an instance of the helper
        helper = AzurePostgresHelper()

        # Act & Assert: Ensure that the exception is raised and the error is logged
        with self.assertRaises(Exception):
            helper.delete_documents(ids_to_delete)

        mock_logger.error.assert_called_with(
            "Unexpected error while deleting documents: Unexpected error"
        )
        mock_connection.rollback.assert_called_once()
        mock_connection.close.assert_called_once()

    @patch(
        "backend.batch.utilities.helpers.azure_postgres_helper.DefaultAzureCredential"
    )
    @patch("backend.batch.utilities.helpers.azure_postgres_helper.psycopg2.connect")
    @patch("backend.batch.utilities.helpers.azure_postgres_helper.logger")
    @patch("backend.batch.utilities.helpers.azure_postgres_helper.EnvHelper")
    def test_perform_search_success(
        self, mock_env_helper, mock_logger, mock_connect, mock_credential
    ):
        # Arrange: Mock the EnvHelper attributes
        mock_env_helper.POSTGRESQL_USER = "mock_user"
        mock_env_helper.POSTGRESQL_HOST = "mock_host"
        mock_env_helper.POSTGRESQL_DATABASE = "mock_database"
        mock_env_helper.AZURE_POSTGRES_SEARCH_TOP_K = 5

        # Mock access token retrieval
        mock_access_token = MagicMock()
        mock_access_token.token = "mock-access-token"
        mock_credential.return_value.get_token.return_value = mock_access_token

        # Mock the connection and cursor
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value = mock_connection

        # Mock the behavior of cursor's execute and fetchall
        mock_cursor.fetchall.return_value = [
            {
                "title": "Test Title",
                "content": "Test Content",
                "metadata": "Test Metadata",
            }
        ]

        title_to_search = "Test Title"

        # Create an instance of the helper
        helper = AzurePostgresHelper()

        # Act: Call the method under test
        result = helper.perform_search(title_to_search)

        # Assert: Check that the results match the expected data
        self.assertEqual(len(result), 1)  # One result returned
        self.assertEqual(result[0]["title"], "Test Title")
        self.assertEqual(result[0]["content"], "Test Content")
        self.assertEqual(result[0]["metadata"], "Test Metadata")

        # Ensure the connection was closed
        mock_connection.close.assert_called_once()
        mock_logger.info.assert_called_with("Retrieved 1 search result(s).")

    @patch(
        "backend.batch.utilities.helpers.azure_postgres_helper.DefaultAzureCredential"
    )
    @patch("backend.batch.utilities.helpers.azure_postgres_helper.psycopg2.connect")
    @patch("backend.batch.utilities.helpers.azure_postgres_helper.logger")
    @patch("backend.batch.utilities.helpers.azure_postgres_helper.EnvHelper")
    def test_perform_search_no_results(
        self, mock_env_helper, mock_logger, mock_connect, mock_credential
    ):
        # Arrange: Mock the EnvHelper attributes
        mock_env_helper.POSTGRESQL_USER = "mock_user"
        mock_env_helper.POSTGRESQL_HOST = "mock_host"
        mock_env_helper.POSTGRESQL_DATABASE = "mock_database"
        mock_env_helper.AZURE_POSTGRES_SEARCH_TOP_K = 5

        # Mock access token retrieval
        mock_access_token = MagicMock()
        mock_access_token.token = "mock-access-token"
        mock_credential.return_value.get_token.return_value = mock_access_token

        # Mock the connection and cursor
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value = mock_connection

        # Mock the behavior of cursor's execute and fetchall to return no results
        mock_cursor.fetchall.return_value = []

        title_to_search = "Nonexistent Title"

        # Create an instance of the helper
        helper = AzurePostgresHelper()

        # Act: Call the method under test
        result = helper.perform_search(title_to_search)

        # Assert: Check that no results were returned
        self.assertEqual(result, [])  # Empty list returned for no results

        # Ensure the connection was closed
        mock_connection.close.assert_called_once()
        mock_logger.info.assert_called_with("Retrieved 0 search result(s).")

    @patch(
        "backend.batch.utilities.helpers.azure_postgres_helper.DefaultAzureCredential"
    )
    @patch("backend.batch.utilities.helpers.azure_postgres_helper.psycopg2.connect")
    @patch("backend.batch.utilities.helpers.azure_postgres_helper.logger")
    @patch("backend.batch.utilities.helpers.azure_postgres_helper.EnvHelper")
    def test_perform_search_error(
        self, mock_env_helper, mock_logger, mock_connect, mock_credential
    ):
        # Arrange: Mock the EnvHelper attributes
        mock_env_helper.POSTGRESQL_USER = "mock_user"
        mock_env_helper.POSTGRESQL_HOST = "mock_host"
        mock_env_helper.POSTGRESQL_DATABASE = "mock_database"
        mock_env_helper.AZURE_POSTGRES_SEARCH_TOP_K = 5

        # Mock access token retrieval
        mock_access_token = MagicMock()
        mock_access_token.token = "mock-access-token"
        mock_credential.return_value.get_token.return_value = mock_access_token

        # Mock the connection and cursor
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value = mock_connection

        # Simulate an error during the execution of the query
        mock_cursor.execute.side_effect = Exception("Database error")

        title_to_search = "Test Title"

        # Create an instance of the helper
        helper = AzurePostgresHelper()

        # Act & Assert: Ensure that the exception is raised and the error is logged
        with self.assertRaises(Exception):
            helper.perform_search(title_to_search)

        mock_logger.error.assert_called_with(
            "Error executing search query: Database error"
        )
        mock_connection.close.assert_called_once()

    @patch(
        "backend.batch.utilities.helpers.azure_postgres_helper.DefaultAzureCredential"
    )
    @patch("backend.batch.utilities.helpers.azure_postgres_helper.psycopg2.connect")
    @patch("backend.batch.utilities.helpers.azure_postgres_helper.logger")
    @patch("backend.batch.utilities.helpers.azure_postgres_helper.EnvHelper")
    def test_get_unique_files_success(
        self, mock_env_helper, mock_logger, mock_connect, mock_credential
    ):
        # Arrange: Mock the EnvHelper attributes
        mock_env_helper.POSTGRESQL_USER = "mock_user"
        mock_env_helper.POSTGRESQL_HOST = "mock_host"
        mock_env_helper.POSTGRESQL_DATABASE = "mock_database"
        mock_env_helper.AZURE_POSTGRES_SEARCH_TOP_K = 5

        # Mock access token retrieval
        mock_access_token = MagicMock()
        mock_access_token.token = "mock-access-token"
        mock_credential.return_value.get_token.return_value = mock_access_token

        # Mock the connection and cursor
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value = mock_connection

        # Mock the behavior of cursor's execute and fetchall
        mock_cursor.fetchall.return_value = [
            {"title": "Unique Title 1"},
            {"title": "Unique Title 2"},
        ]

        # Create an instance of the helper
        helper = AzurePostgresHelper()

        # Act: Call the method under test
        result = helper.get_unique_files()

        # Assert: Check that the results match the expected data
        self.assertEqual(len(result), 2)  # Two unique titles returned
        self.assertEqual(result[0]["title"], "Unique Title 1")
        self.assertEqual(result[1]["title"], "Unique Title 2")

        # Ensure the connection was closed
        mock_connection.close.assert_called_once()
        mock_logger.info.assert_called_with("Retrieved 2 unique title(s).")

    @patch(
        "backend.batch.utilities.helpers.azure_postgres_helper.DefaultAzureCredential"
    )
    @patch("backend.batch.utilities.helpers.azure_postgres_helper.psycopg2.connect")
    @patch("backend.batch.utilities.helpers.azure_postgres_helper.logger")
    @patch("backend.batch.utilities.helpers.azure_postgres_helper.EnvHelper")
    def test_get_unique_files_no_results(
        self, mock_env_helper, mock_logger, mock_connect, mock_credential
    ):
        # Arrange: Mock the EnvHelper attributes
        mock_env_helper.POSTGRESQL_USER = "mock_user"
        mock_env_helper.POSTGRESQL_HOST = "mock_host"
        mock_env_helper.POSTGRESQL_DATABASE = "mock_database"
        mock_env_helper.AZURE_POSTGRES_SEARCH_TOP_K = 5

        # Mock access token retrieval
        mock_access_token = MagicMock()
        mock_access_token.token = "mock-access-token"
        mock_credential.return_value.get_token.return_value = mock_access_token

        # Mock the connection and cursor
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value = mock_connection

        # Mock the behavior of cursor's execute and fetchall to return no results
        mock_cursor.fetchall.return_value = []

        # Create an instance of the helper
        helper = AzurePostgresHelper()

        # Act: Call the method under test
        result = helper.get_unique_files()

        # Assert: Check that no results were returned
        self.assertEqual(result, [])  # Empty list returned for no results

        # Ensure the connection was closed
        mock_connection.close.assert_called_once()
        mock_logger.info.assert_called_with("Retrieved 0 unique title(s).")

    @patch(
        "backend.batch.utilities.helpers.azure_postgres_helper.DefaultAzureCredential"
    )
    @patch("backend.batch.utilities.helpers.azure_postgres_helper.psycopg2.connect")
    @patch("backend.batch.utilities.helpers.azure_postgres_helper.logger")
    @patch("backend.batch.utilities.helpers.azure_postgres_helper.EnvHelper")
    def test_get_unique_files_error(
        self, mock_env_helper, mock_logger, mock_connect, mock_credential
    ):
        # Arrange: Mock the EnvHelper attributes
        mock_env_helper.POSTGRESQL_USER = "mock_user"
        mock_env_helper.POSTGRESQL_HOST = "mock_host"
        mock_env_helper.POSTGRESQL_DATABASE = "mock_database"
        mock_env_helper.AZURE_POSTGRES_SEARCH_TOP_K = 5

        # Mock access token retrieval
        mock_access_token = MagicMock()
        mock_access_token.token = "mock-access-token"
        mock_credential.return_value.get_token.return_value = mock_access_token

        # Mock the connection and cursor
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value = mock_connection

        # Simulate an error during the execution of the query
        mock_cursor.execute.side_effect = Exception("Database error")

        # Create an instance of the helper
        helper = AzurePostgresHelper()

        # Act & Assert: Ensure that the exception is raised and the error is logged
        with self.assertRaises(Exception):
            helper.get_unique_files()

        mock_logger.error.assert_called_with(
            "Error executing search query: Database error"
        )
        mock_connection.close.assert_called_once()

    @patch(
        "backend.batch.utilities.helpers.azure_postgres_helper.DefaultAzureCredential"
    )
    @patch("backend.batch.utilities.helpers.azure_postgres_helper.psycopg2.connect")
    @patch("backend.batch.utilities.helpers.azure_postgres_helper.logger")
    @patch("backend.batch.utilities.helpers.azure_postgres_helper.EnvHelper")
    def test_search_by_blob_url_success(
        self, mock_env_helper, mock_logger, mock_connect, mock_credential
    ):
        # Arrange: Mock the EnvHelper attributes
        mock_env_helper.POSTGRESQL_USER = "mock_user"
        mock_env_helper.POSTGRESQL_HOST = "mock_host"
        mock_env_helper.POSTGRESQL_DATABASE = "mock_database"
        mock_env_helper.AZURE_POSTGRES_SEARCH_TOP_K = 5

        # Mock access token retrieval
        mock_access_token = MagicMock()
        mock_access_token.token = "mock-access-token"
        mock_credential.return_value.get_token.return_value = mock_access_token

        # Mock the connection and cursor
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value = mock_connection

        # Mock the behavior of cursor's execute and fetchall
        mock_cursor.fetchall.return_value = [
            {"id": 1, "title": "Title 1"},
            {"id": 2, "title": "Title 2"},
        ]

        # Create an instance of the helper
        helper = AzurePostgresHelper()
        blob_url = "mock_blob_url"

        # Act: Call the method under test
        result = helper.search_by_blob_url(blob_url)

        # Assert: Check that the results match the expected data
        self.assertEqual(len(result), 2)  # Two titles returned
        self.assertEqual(result[0]["title"], "Title 1")
        self.assertEqual(result[1]["title"], "Title 2")

        # Ensure the connection was closed
        mock_connection.close.assert_called_once()
        mock_logger.info.assert_called_with("Retrieved 2 unique title(s).")

    @patch(
        "backend.batch.utilities.helpers.azure_postgres_helper.DefaultAzureCredential"
    )
    @patch("backend.batch.utilities.helpers.azure_postgres_helper.psycopg2.connect")
    @patch("backend.batch.utilities.helpers.azure_postgres_helper.logger")
    @patch("backend.batch.utilities.helpers.azure_postgres_helper.EnvHelper")
    def test_search_by_blob_url_no_results(
        self, mock_env_helper, mock_logger, mock_connect, mock_credential
    ):
        # Arrange: Mock the EnvHelper attributes
        mock_env_helper.POSTGRESQL_USER = "mock_user"
        mock_env_helper.POSTGRESQL_HOST = "mock_host"
        mock_env_helper.POSTGRESQL_DATABASE = "mock_database"
        mock_env_helper.AZURE_POSTGRES_SEARCH_TOP_K = 5

        # Mock access token retrieval
        mock_access_token = MagicMock()
        mock_access_token.token = "mock-access-token"
        mock_credential.return_value.get_token.return_value = mock_access_token

        # Mock the connection and cursor
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value = mock_connection

        # Mock the behavior of cursor's execute and fetchall to return no results
        mock_cursor.fetchall.return_value = []

        # Create an instance of the helper
        helper = AzurePostgresHelper()
        blob_url = "mock_blob_url"

        # Act: Call the method under test
        result = helper.search_by_blob_url(blob_url)

        # Assert: Check that no results were returned
        self.assertEqual(result, [])  # Empty list returned for no results

        # Ensure the connection was closed
        mock_connection.close.assert_called_once()
        mock_logger.info.assert_called_with("Retrieved 0 unique title(s).")

    @patch(
        "backend.batch.utilities.helpers.azure_postgres_helper.DefaultAzureCredential"
    )
    @patch("backend.batch.utilities.helpers.azure_postgres_helper.psycopg2.connect")
    @patch("backend.batch.utilities.helpers.azure_postgres_helper.logger")
    @patch("backend.batch.utilities.helpers.azure_postgres_helper.EnvHelper")
    def test_search_by_blob_url_error(
        self, mock_env_helper, mock_logger, mock_connect, mock_credential
    ):
        # Arrange: Mock the EnvHelper attributes
        mock_env_helper.POSTGRESQL_USER = "mock_user"
        mock_env_helper.POSTGRESQL_HOST = "mock_host"
        mock_env_helper.POSTGRESQL_DATABASE = "mock_database"
        mock_env_helper.AZURE_POSTGRES_SEARCH_TOP_K = 5

        # Mock access token retrieval
        mock_access_token = MagicMock()
        mock_access_token.token = "mock-access-token"
        mock_credential.return_value.get_token.return_value = mock_access_token

        # Mock the connection and cursor
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value = mock_connection

        # Simulate an error during the execution of the query
        mock_cursor.execute.side_effect = Exception("Database error")

        # Create an instance of the helper
        helper = AzurePostgresHelper()
        blob_url = "mock_blob_url"

        # Act & Assert: Ensure that the exception is raised and the error is logged
        with self.assertRaises(Exception):
            helper.search_by_blob_url(blob_url)

        mock_logger.error.assert_called_with(
            "Error executing search query: Database error"
        )
        mock_connection.close.assert_called_once()
