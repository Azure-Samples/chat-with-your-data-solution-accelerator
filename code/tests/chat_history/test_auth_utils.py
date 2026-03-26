"""
Unit tests for auth_utils.py
Tests authentication utility functions for EasyAuth header processing.
"""

import base64
import json
from unittest.mock import patch, MagicMock

from backend.batch.utilities.chat_history.auth_utils import (
    get_authenticated_user_details,
    get_tenantid,
)


class TestGetAuthenticatedUserDetails:
    """Tests for get_authenticated_user_details function."""

    def test_with_all_easyauth_headers_present(self):
        """Test production mode: extracts all EasyAuth headers into user object."""
        request_headers = {
            "X-Ms-Client-Principal-Id": "test-principal-id",
            "X-Ms-Client-Principal-Name": "test@example.com",
            "X-Ms-Client-Principal-Idp": "aad",
            "X-Ms-Token-Aad-Id-Token": "test-aad-token",
            "X-Ms-Client-Principal": "base64-principal-data",
        }

        result = get_authenticated_user_details(request_headers)

        # Business logic: maps specific EasyAuth headers to user object fields
        assert result["user_principal_id"] == "test-principal-id"
        assert result["user_name"] == "test@example.com"
        assert result["auth_provider"] == "aad"
        assert result["aad_id_token"] == "test-aad-token"
        assert result["client_principal_b64"] == "base64-principal-data"
        assert result["auth_token"] == "test-aad-token"

    def test_without_principal_id_header_uses_sample_user(self):
        """Test development mode: falls back to sample user when principal ID missing."""
        request_headers = {
            "Content-Type": "application/json",
            "Host": "localhost",
        }

        mock_sample_user = MagicMock()
        mock_sample_user.sample_user = {
            "X-Ms-Client-Principal-Id": "sample-principal-id",
            "X-Ms-Client-Principal-Name": "sample@example.com",
            "X-Ms-Client-Principal-Idp": "aad",
            "X-Ms-Token-Aad-Id-Token": "sample-aad-token",
            "X-Ms-Client-Principal": "sample-base64-data",
        }

        with patch.dict(
            "sys.modules",
            {"backend.batch.utilities.chat_history.sample_user": mock_sample_user},
        ):
            result = get_authenticated_user_details(request_headers)

            # Business logic: dev mode uses sample_user instead of request headers
            assert result["user_principal_id"] == "sample-principal-id"
            assert result["user_name"] == "sample@example.com"
            assert result["auth_provider"] == "aad"

    def test_extracts_correct_header_keys(self):
        """Test header mapping: verifies correct EasyAuth headers are mapped to user fields."""
        request_headers = {
            "X-Ms-Client-Principal-Id": "principal-123",
            "X-Ms-Client-Principal-Name": "user@domain.com",
            "X-Ms-Client-Principal-Idp": "github",
            "X-Ms-Token-Aad-Id-Token": "token-abc",
            "X-Ms-Client-Principal": "encoded-data",
            "Other-Header": "ignored-value",
        }

        result = get_authenticated_user_details(request_headers)

        # Business logic: only specific headers are extracted, others ignored
        assert result["user_principal_id"] == "principal-123"
        assert result["user_name"] == "user@domain.com"
        assert result["auth_provider"] == "github"
        assert result["aad_id_token"] == "token-abc"
        assert result["client_principal_b64"] == "encoded-data"
        assert result["auth_token"] == "token-abc"


class TestGetTenantId:
    """Tests for get_tenantid function."""

    def test_with_valid_base64_and_valid_json_returns_tenant_id(self):
        """Test successful path: base64 decode → JSON parse → extract tid."""
        tenant_data = {"tid": "tenant-12345"}
        json_str = json.dumps(tenant_data)
        base64_encoded = base64.b64encode(json_str.encode("utf-8")).decode("utf-8")

        result = get_tenantid(base64_encoded)

        # Business logic: extracts tenant ID from encoded principal
        assert result == "tenant-12345"

    def test_with_invalid_base64_returns_empty_string(self):
        """Test error handling: invalid base64 returns empty string and logs exception."""
        invalid_base64 = "not-valid-base64!!!"

        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            result = get_tenantid(invalid_base64)

            # Business logic: error handling returns empty string
            assert result == ""
            mock_logger.exception.assert_called_once()

    def test_with_valid_base64_invalid_json_returns_empty_string(self):
        """Test error handling: valid base64 but invalid JSON returns empty string."""
        invalid_json = "not valid json"
        base64_encoded = base64.b64encode(invalid_json.encode("utf-8")).decode("utf-8")

        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            result = get_tenantid(base64_encoded)

            # Business logic: JSON parsing error returns empty string
            assert result == ""
            mock_logger.exception.assert_called_once()

    def test_with_none_input_returns_empty_string(self):
        """Test guard clause: None input bypassed by if check, returns empty string."""
        result = get_tenantid(None)

        # Business logic: if check protects against None input
        assert result == ""

    def test_base64_decoding_process(self):
        """Test full pipeline: verifies only tid field extracted, other fields ignored."""
        tenant_data = {
            "tid": "complex-tenant-id-abc-123",
            "sub": "subject-id",
            "name": "Test User",
            "roles": ["admin", "user"],
        }
        json_str = json.dumps(tenant_data)
        base64_encoded = base64.b64encode(json_str.encode("utf-8")).decode("utf-8")

        result = get_tenantid(base64_encoded)

        # Business logic: only 'tid' field is extracted from principal
        assert result == "complex-tenant-id-abc-123"
