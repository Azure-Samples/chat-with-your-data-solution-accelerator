"""Unit tests for the combine_pages_chunknos Azure Function."""

import sys
import json
from unittest.mock import MagicMock


class MockHttpResponse:
    def __init__(self, body, mimetype, status_code):
        self._body = body
        self.mimetype = mimetype
        self.status_code = status_code

    def get_body(self):
        return self._body.encode() if isinstance(self._body, str) else self._body


class MockBlueprint:
    def route(self, **kwargs):
        def decorator(func):
            return func
        return decorator


# Mock azure.functions before importing the module under test
mock_func = MagicMock()
mock_func.HttpRequest = MagicMock
mock_func.HttpResponse = MockHttpResponse
mock_func.Blueprint = MockBlueprint
mock_func.AuthLevel = MagicMock()
mock_func.AuthLevel.ANONYMOUS = 0
sys.modules['azure.functions'] = mock_func


class TestCombinePagesAndChunkNos:
    """Tests for the combine_pages_and_chunknos Azure Function."""

    @staticmethod
    def _get_combine_function():
        """Lazy import of the function under test."""
        from backend.batch.combine_pages_chunknos import combine_pages_and_chunknos
        return combine_pages_and_chunknos

    @staticmethod
    def _create_request(values):
        """Helper to create mock request."""
        mock_request = MagicMock()
        mock_request.get_json.return_value = {"values": values}
        return mock_request

    @staticmethod
    def _parse_response(response):
        """Helper to parse response body."""
        body = response.get_body()
        if isinstance(body, bytes):
            body = body.decode()
        return json.loads(body)

    def test_combines_pages_and_chunknos(self):
        """Test array zipping logic creates correct page_text/chunk_no objects."""
        combine_pages_and_chunknos = self._get_combine_function()
        request = self._create_request([{
            "recordId": "1",
            "data": {"pages": ["Page 1", "Page 2", "Page 3"], "chunk_nos": [1, 2, 3]}
        }])

        response = combine_pages_and_chunknos(request)
        body = self._parse_response(response)

        pages_with_chunks = body["values"][0]["data"]["pages_with_chunks"]
        assert pages_with_chunks == [
            {"page_text": "Page 1", "chunk_no": 1},
            {"page_text": "Page 2", "chunk_no": 2},
            {"page_text": "Page 3", "chunk_no": 3}
        ]

    def test_processes_multiple_records(self):
        """Test for loop processes all records."""
        combine_pages_and_chunknos = self._get_combine_function()
        request = self._create_request([
            {"recordId": "1", "data": {"pages": ["P1"], "chunk_nos": [1]}},
            {"recordId": "2", "data": {"pages": ["P2"], "chunk_nos": [2]}}
        ])

        response = combine_pages_and_chunknos(request)
        body = self._parse_response(response)

        assert len(body["values"]) == 2
        assert body["values"][0]["recordId"] == "1"
        assert body["values"][1]["recordId"] == "2"

    def test_handles_empty_arrays(self):
        """Test edge case with empty input arrays."""
        combine_pages_and_chunknos = self._get_combine_function()
        request = self._create_request([{
            "recordId": "1",
            "data": {"pages": [], "chunk_nos": []}
        }])

        response = combine_pages_and_chunknos(request)
        body = self._parse_response(response)

        assert body["values"][0]["data"]["pages_with_chunks"] == []

    def test_handles_json_parse_errors(self):
        """Test custom error handling returns 500 with error details."""
        combine_pages_and_chunknos = self._get_combine_function()
        mock_request = MagicMock()
        mock_request.get_json.side_effect = ValueError("Invalid JSON")

        response = combine_pages_and_chunknos(mock_request)
        body = self._parse_response(response)

        assert response.status_code == 500
        assert "error" in body["values"][0]["recordId"]
        assert body["values"][0]["errors"]

    def test_returns_webapiskill_format(self):
        """Test response structure matches WebApiSkill specification."""
        combine_pages_and_chunknos = self._get_combine_function()
        request = self._create_request([{
            "recordId": "test-123",
            "data": {"pages": ["Test"], "chunk_nos": [1]}
        }])

        response = combine_pages_and_chunknos(request)
        body = self._parse_response(response)
        value = body["values"][0]

        assert response.status_code == 200
        assert value.keys() == {"recordId", "data", "errors", "warnings"}
        assert value["errors"] is None
        assert value["warnings"] is None

    def test_preserves_record_id(self):
        """Test recordId flows through unchanged."""
        combine_pages_and_chunknos = self._get_combine_function()
        request = self._create_request([{
            "recordId": "unique-id-12345",
            "data": {"pages": ["Test"], "chunk_nos": [999]}
        }])

        response = combine_pages_and_chunknos(request)
        body = self._parse_response(response)

        assert body["values"][0]["recordId"] == "unique-id-12345"
