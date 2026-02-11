"""
Unit tests for azure_form_recognizer_helper.py module.
Tests focus on actual business logic: table HTML generation, document analysis workflow,
and role-based HTML conversion.
"""

import html
from unittest.mock import Mock, patch

import pytest

from backend.batch.utilities.helpers.azure_form_recognizer_helper import AzureFormRecognizerClient


@pytest.fixture(autouse=True)
def mock_env_helper():
    """Mock EnvHelper with different auth configurations."""
    with patch("backend.batch.utilities.helpers.azure_form_recognizer_helper.EnvHelper") as mock:
        env = Mock()
        env.AZURE_FORM_RECOGNIZER_ENDPOINT = "https://test-endpoint.cognitiveservices.azure.com/"
        env.AZURE_FORM_RECOGNIZER_KEY = "test-key-12345"
        env.AZURE_AUTH_TYPE = "keys"
        env.MANAGED_IDENTITY_CLIENT_ID = None
        mock.return_value = env
        yield env


@pytest.fixture
def mock_env_helper_rbac():
    """Mock EnvHelper with RBAC auth configuration."""
    with patch("backend.batch.utilities.helpers.azure_form_recognizer_helper.EnvHelper") as mock:
        env = Mock()
        env.AZURE_FORM_RECOGNIZER_ENDPOINT = "https://test-endpoint.cognitiveservices.azure.com/"
        env.AZURE_AUTH_TYPE = "rbac"
        env.MANAGED_IDENTITY_CLIENT_ID = "test-client-id"
        mock.return_value = env
        yield env


class TestAzureFormRecognizerClientInitialization:
    """Tests for client initialization with different auth types."""

    @patch("backend.batch.utilities.helpers.azure_form_recognizer_helper.DocumentAnalysisClient")
    @patch("backend.batch.utilities.helpers.azure_form_recognizer_helper.AzureKeyCredential")
    def test_initialization_with_key_auth(self, mock_credential, mock_client, mock_env_helper):
        """Test client initializes correctly with key-based authentication."""
        client = AzureFormRecognizerClient()

        mock_credential.assert_called_once_with("test-key-12345")
        mock_client.assert_called_once()
        assert client.AZURE_FORM_RECOGNIZER_ENDPOINT == "https://test-endpoint.cognitiveservices.azure.com/"
        assert client.AZURE_FORM_RECOGNIZER_KEY == "test-key-12345"

    @patch("backend.batch.utilities.helpers.azure_form_recognizer_helper.DocumentAnalysisClient")
    @patch("backend.batch.utilities.helpers.azure_form_recognizer_helper.get_azure_credential")
    def test_initialization_with_rbac_auth(self, mock_get_credential, mock_client, mock_env_helper_rbac):
        """Test client initializes correctly with RBAC authentication."""
        mock_credential = Mock()
        mock_get_credential.return_value = mock_credential

        AzureFormRecognizerClient()

        mock_get_credential.assert_called_once_with("test-client-id")
        mock_client.assert_called_once()
        call_kwargs = mock_client.call_args[1]
        assert call_kwargs['endpoint'] == "https://test-endpoint.cognitiveservices.azure.com/"
        assert call_kwargs['credential'] == mock_credential
        assert 'chat-with-your-data-solution-accelerator' in call_kwargs['headers']['x-ms-useragent']


class TestTableToHTML:
    """Tests for _table_to_html method - core business logic."""

    @patch("backend.batch.utilities.helpers.azure_form_recognizer_helper.DocumentAnalysisClient")
    def test_simple_table_conversion(self, mock_client):
        """Test converting a simple 2x2 table to HTML."""
        client = AzureFormRecognizerClient()

        # Create mock table with 2 rows, 2 columns
        mock_table = Mock()
        mock_table.row_count = 2
        mock_table.cells = [
            Mock(row_index=0, column_index=0, kind="columnHeader", content="Header 1", column_span=1, row_span=1),
            Mock(row_index=0, column_index=1, kind="columnHeader", content="Header 2", column_span=1, row_span=1),
            Mock(row_index=1, column_index=0, kind="content", content="Cell 1", column_span=1, row_span=1),
            Mock(row_index=1, column_index=1, kind="content", content="Cell 2", column_span=1, row_span=1),
        ]

        result = client._table_to_html(mock_table)

        assert result.startswith("<table>")
        assert result.endswith("</table>")
        assert "<th>Header 1</th>" in result
        assert "<th>Header 2</th>" in result
        assert "<td>Cell 1</td>" in result
        assert "<td>Cell 2</td>" in result
        assert result.count("<tr>") == 2
        assert result.count("</tr>") == 2

    @patch("backend.batch.utilities.helpers.azure_form_recognizer_helper.DocumentAnalysisClient")
    def test_table_with_colspan(self, mock_client):
        """Test table cell with column span."""
        client = AzureFormRecognizerClient()

        mock_table = Mock()
        mock_table.row_count = 2
        mock_table.cells = [
            Mock(row_index=0, column_index=0, kind="columnHeader", content="Merged Header", column_span=2, row_span=1),
            Mock(row_index=1, column_index=0, kind="content", content="Cell 1", column_span=1, row_span=1),
            Mock(row_index=1, column_index=1, kind="content", content="Cell 2", column_span=1, row_span=1),
        ]

        result = client._table_to_html(mock_table)

        assert ' colSpan=2' in result
        assert "Merged Header" in result

    @patch("backend.batch.utilities.helpers.azure_form_recognizer_helper.DocumentAnalysisClient")
    def test_table_with_rowspan(self, mock_client):
        """Test table cell with row span."""
        client = AzureFormRecognizerClient()

        mock_table = Mock()
        mock_table.row_count = 2
        mock_table.cells = [
            Mock(row_index=0, column_index=0, kind="rowHeader", content="Row Header", column_span=1, row_span=2),
            Mock(row_index=0, column_index=1, kind="content", content="Cell 1", column_span=1, row_span=1),
            Mock(row_index=1, column_index=1, kind="content", content="Cell 2", column_span=1, row_span=1),
        ]

        result = client._table_to_html(mock_table)

        assert ' rowSpan=2' in result
        assert "Row Header" in result

    @patch("backend.batch.utilities.helpers.azure_form_recognizer_helper.DocumentAnalysisClient")
    def test_table_html_escapes_content(self, mock_client):
        """Test that table content is HTML-escaped to prevent XSS."""
        client = AzureFormRecognizerClient()

        mock_table = Mock()
        mock_table.row_count = 1
        mock_table.cells = [
            Mock(row_index=0, column_index=0, kind="content",
                 content="<script>alert('xss')</script>", column_span=1, row_span=1),
        ]

        result = client._table_to_html(mock_table)

        assert "<script>alert('xss')</script>" not in result
        assert html.escape("<script>alert('xss')</script>") in result

    @patch("backend.batch.utilities.helpers.azure_form_recognizer_helper.DocumentAnalysisClient")
    def test_table_cells_sorted_by_column_index(self, mock_client):
        """Test that cells are sorted by column index within each row."""
        client = AzureFormRecognizerClient()

        # Create cells in wrong order
        mock_table = Mock()
        mock_table.row_count = 1
        mock_table.cells = [
            Mock(row_index=0, column_index=2, kind="content", content="Third", column_span=1, row_span=1),
            Mock(row_index=0, column_index=0, kind="content", content="First", column_span=1, row_span=1),
            Mock(row_index=0, column_index=1, kind="content", content="Second", column_span=1, row_span=1),
        ]

        result = client._table_to_html(mock_table)

        # Verify order by checking positions in result string
        first_pos = result.find("First")
        second_pos = result.find("Second")
        third_pos = result.find("Third")

        assert first_pos < second_pos < third_pos


class TestBeginAnalyzeDocumentFromUrl:
    """Tests for the main document analysis workflow."""

    @patch("backend.batch.utilities.helpers.azure_form_recognizer_helper.DocumentAnalysisClient")
    def test_analyze_document_uses_layout_model(self, mock_client_class):
        """Test that layout model is used when use_layout=True."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        mock_poller = Mock()
        mock_result = Mock()
        mock_result.paragraphs = []
        mock_result.pages = [Mock(spans=[Mock(offset=0, length=10)])]
        mock_result.tables = []
        mock_result.content = "Test content"
        mock_poller.result.return_value = mock_result

        mock_client.begin_analyze_document_from_url.return_value = mock_poller

        client = AzureFormRecognizerClient()
        client.begin_analyze_document_from_url("https://example.com/doc.pdf", use_layout=True)

        mock_client.begin_analyze_document_from_url.assert_called_once_with(
            "prebuilt-layout", document_url="https://example.com/doc.pdf"
        )

    @patch("backend.batch.utilities.helpers.azure_form_recognizer_helper.DocumentAnalysisClient")
    def test_analyze_document_uses_read_model(self, mock_client_class):
        """Test that read model is used when use_layout=False."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        mock_poller = Mock()
        mock_result = Mock()
        mock_result.paragraphs = []
        mock_result.pages = [Mock(spans=[Mock(offset=0, length=10)])]
        mock_result.tables = []
        mock_result.content = "Test content"
        mock_poller.result.return_value = mock_result

        mock_client.begin_analyze_document_from_url.return_value = mock_poller

        client = AzureFormRecognizerClient()
        client.begin_analyze_document_from_url("https://example.com/doc.pdf", use_layout=False)

        mock_client.begin_analyze_document_from_url.assert_called_once_with(
            "prebuilt-read", document_url="https://example.com/doc.pdf"
        )

    @patch("backend.batch.utilities.helpers.azure_form_recognizer_helper.DocumentAnalysisClient")
    def test_analyze_document_returns_page_map(self, mock_client_class):
        """Test that document analysis returns correct page map structure."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        mock_poller = Mock()
        mock_result = Mock()
        mock_result.paragraphs = []
        mock_result.tables = []

        # Content must match the total length of all page spans
        content_page1 = "Page 1 content!"  # 15 chars (offset 0-14)
        content_page2 = "Page 2 content!"  # 15 chars (offset 15-29)
        mock_result.content = content_page1 + content_page2  # 30 chars total

        # Create two pages with correct spans matching content length
        mock_result.pages = [
            Mock(spans=[Mock(offset=0, length=15)]),
            Mock(spans=[Mock(offset=15, length=15)])
        ]

        mock_poller.result.return_value = mock_result
        mock_client.begin_analyze_document_from_url.return_value = mock_poller

        client = AzureFormRecognizerClient()
        result = client.begin_analyze_document_from_url("https://example.com/doc.pdf")

        assert len(result) == 2
        assert result[0]['page_number'] == 0
        assert result[1]['page_number'] == 1
        assert result[0]['offset'] == 0
        # Verify page_text contains content
        assert len(result[0]['page_text']) > 0
        assert 'page_text' in result[1]

    @patch("backend.batch.utilities.helpers.azure_form_recognizer_helper.DocumentAnalysisClient")
    def test_analyze_document_handles_paragraphs_with_roles(self, mock_client_class):
        """Test that paragraph roles are converted to HTML tags."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        mock_poller = Mock()
        mock_result = Mock()

        # Create paragraph with title role spanning full content
        mock_paragraph = Mock()
        mock_paragraph.role = "title"
        mock_paragraph.spans = [Mock(offset=0, length=10)]
        mock_result.paragraphs = [mock_paragraph]

        mock_result.tables = []
        mock_result.content = "Title Text"  # 10 chars
        mock_result.pages = [Mock(spans=[Mock(offset=0, length=10)])]

        mock_poller.result.return_value = mock_result
        mock_client.begin_analyze_document_from_url.return_value = mock_poller

        client = AzureFormRecognizerClient()
        result = client.begin_analyze_document_from_url("https://example.com/doc.pdf")

        # Title role should be converted to h1 tags (opening tag at start, may not have closing)
        assert '<h1>' in result[0]['page_text']
        assert 'Title Text' in result[0]['page_text']

    @patch("backend.batch.utilities.helpers.azure_form_recognizer_helper.DocumentAnalysisClient")
    def test_analyze_document_raises_error_on_failure(self, mock_client_class):
        """Test that analysis errors are properly wrapped and raised."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        mock_client.begin_analyze_document_from_url.side_effect = Exception("API Error")

        client = AzureFormRecognizerClient()

        with pytest.raises(ValueError) as exc_info:
            client.begin_analyze_document_from_url("https://example.com/doc.pdf")

        assert "Error:" in str(exc_info.value)


class TestDocumentAnalysisIntegration:
    """Integration tests for document analysis with tables and roles."""

    @patch("backend.batch.utilities.helpers.azure_form_recognizer_helper.DocumentAnalysisClient")
    def test_analyze_document_integrates_tables_into_page_text(self, mock_client_class):
        """Test that tables are converted to HTML and integrated into page text."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # Create a table that spans part of the page
        mock_table = Mock()
        mock_table.row_count = 1
        mock_table.bounding_regions = [Mock(page_number=1)]
        mock_table.spans = [Mock(offset=5, length=10)]
        mock_table.cells = [
            Mock(row_index=0, column_index=0, kind="content", content="Data", column_span=1, row_span=1)
        ]

        mock_poller = Mock()
        mock_result = Mock()
        mock_result.paragraphs = []
        mock_result.tables = [mock_table]
        mock_result.content = "Text [TABLE_DATA] More"  # 22 chars total
        mock_result.pages = [Mock(spans=[Mock(offset=0, length=22)])]

        mock_poller.result.return_value = mock_result
        mock_client.begin_analyze_document_from_url.return_value = mock_poller

        client = AzureFormRecognizerClient()
        result = client.begin_analyze_document_from_url("https://example.com/doc.pdf")

        # Verify table HTML is in page_text
        assert '<table>' in result[0]['page_text']
        assert '<td>Data</td>' in result[0]['page_text']

    @patch("backend.batch.utilities.helpers.azure_form_recognizer_helper.DocumentAnalysisClient")
    def test_analyze_document_combines_roles_and_content(self, mock_client_class):
        """Test that multiple paragraph roles are correctly applied to content."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # Create multiple paragraphs with different roles
        mock_title = Mock()
        mock_title.role = "title"
        mock_title.spans = [Mock(offset=0, length=5)]

        mock_section = Mock()
        mock_section.role = "sectionHeading"
        mock_section.spans = [Mock(offset=6, length=7)]

        mock_poller = Mock()
        mock_result = Mock()
        mock_result.paragraphs = [mock_title, mock_section]
        mock_result.tables = []
        mock_result.content = "Title Section Text"  # 18 chars
        mock_result.pages = [Mock(spans=[Mock(offset=0, length=18)])]

        mock_poller.result.return_value = mock_result
        mock_client.begin_analyze_document_from_url.return_value = mock_poller

        client = AzureFormRecognizerClient()
        result = client.begin_analyze_document_from_url("https://example.com/doc.pdf")

        # Verify both role tags are present
        page_text = result[0]['page_text']
        assert '<h1>' in page_text  # title role
        assert '<h2>' in page_text  # sectionHeading role
