"""Test suite for RAI validator module."""
# pylint: disable=redefined-outer-name  # pytest fixtures
# pylint: disable=protected-access  # accessing _instance for test cleanup

from unittest.mock import Mock, patch

import pytest

from backend.batch.utilities.helpers.rai_validator import (
    RAIValidator,
    _RAIValidatorSingleton,
    get_rai_validator,
    validate_content,
    validate_file_content,
)
from backend.batch.utilities.helpers.env_helper import EnvHelper


@pytest.fixture(autouse=True)
def cleanup_singleton():
    """Clean up singleton instance before and after each test."""
    _RAIValidatorSingleton._instance = None
    yield
    _RAIValidatorSingleton._instance = None


@pytest.fixture
def mock_env_helper():
    """Create a mock EnvHelper for testing."""
    env = Mock(spec=EnvHelper)
    env.AZURE_OPENAI_ENDPOINT = "https://test-openai.openai.azure.com/"
    env.AZURE_OPENAI_API_VERSION = "2024-02-01"
    env.OPENAI_API_KEY = "test-api-key"
    env.AZURE_OPENAI_MODEL = "gpt-4"
    env.AZURE_OPENAI_RAI_DEPLOYMENT_NAME = None
    env.is_auth_type_keys.return_value = True
    env.AZURE_TOKEN_PROVIDER = None
    return env


@pytest.fixture
def mock_openai_client():
    """Create a mock Azure OpenAI client."""
    client = Mock()
    mock_response = Mock()
    mock_choice = Mock()
    mock_message = Mock()
    mock_message.content = "ALLOW"
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    client.chat.completions.create.return_value = mock_response
    return client


class TestRAIValidatorInitialization:
    """Test RAI validator initialization scenarios."""

    def test_initialization_with_api_key_auth(self, mock_env_helper):
        """Test validator initializes with API key authentication."""
        with patch("backend.batch.utilities.helpers.rai_validator.AzureOpenAI") as mock_openai:
            validator = RAIValidator(mock_env_helper)

            assert validator.env_helper == mock_env_helper
            mock_openai.assert_called_once_with(
                azure_endpoint="https://test-openai.openai.azure.com/",
                api_version="2024-02-01",
                api_key="test-api-key",
            )

    def test_initialization_with_rbac_auth(self, mock_env_helper):
        """Test validator initializes with RBAC authentication."""
        mock_env_helper.is_auth_type_keys.return_value = False
        mock_env_helper.AZURE_TOKEN_PROVIDER = Mock()

        with patch("backend.batch.utilities.helpers.rai_validator.AzureOpenAI") as mock_openai:
            validator = RAIValidator(mock_env_helper)

            assert validator.env_helper == mock_env_helper
            mock_openai.assert_called_once_with(
                azure_endpoint="https://test-openai.openai.azure.com/",
                api_version="2024-02-01",
                azure_ad_token_provider=mock_env_helper.AZURE_TOKEN_PROVIDER,
            )

    def test_initialization_without_endpoint(self, mock_env_helper):
        """Test validator handles missing endpoint gracefully."""
        mock_env_helper.AZURE_OPENAI_ENDPOINT = None

        validator = RAIValidator(mock_env_helper)

        assert validator.client is None

    def test_initialization_with_default_env_helper(self):
        """Test validator can initialize with default EnvHelper."""
        with patch("backend.batch.utilities.helpers.rai_validator.EnvHelper") as mock_env_cls:
            with patch("backend.batch.utilities.helpers.rai_validator.AzureOpenAI"):
                validator = RAIValidator()

                assert validator.env_helper is not None
                mock_env_cls.assert_called_once()

    def test_initialization_handles_client_error(self, mock_env_helper):
        """Test validator handles Azure OpenAI client initialization errors."""
        with patch("backend.batch.utilities.helpers.rai_validator.AzureOpenAI", side_effect=Exception("API Error")):
            validator = RAIValidator(mock_env_helper)

            assert validator.client is None


class TestValidateContent:
    """Test content validation functionality."""

    def test_validate_content_allows_safe_content(self, mock_env_helper, mock_openai_client):
        """Test that safe content is allowed."""
        validator = RAIValidator(mock_env_helper)
        validator.client = mock_openai_client

        is_valid, message = validator.validate_content("This is safe educational content about history.")

        assert is_valid is True
        assert message == ""
        mock_openai_client.chat.completions.create.assert_called_once()

    def test_validate_content_blocks_on_block_verdict(self, mock_env_helper, mock_openai_client):
        """Test that content is blocked when verdict is BLOCK."""
        mock_openai_client.chat.completions.create.return_value.choices[0].message.content = "BLOCK"
        validator = RAIValidator(mock_env_helper)
        validator.client = mock_openai_client

        is_valid, message = validator.validate_content("Dangerous content")

        assert is_valid is False
        assert "inappropriate, dangerous, or unsafe" in message

    def test_validate_content_blocks_on_block_content_verdict(self, mock_env_helper, mock_openai_client):
        """Test content blocking with BLOCK_CONTENT verdict."""
        mock_openai_client.chat.completions.create.return_value.choices[0].message.content = "BLOCK_CONTENT"
        validator = RAIValidator(mock_env_helper)
        validator.client = mock_openai_client

        is_valid, message = validator.validate_content("Harmful instructions")

        assert is_valid is False
        assert "content contains inappropriate" in message.lower()

    def test_validate_content_allows_on_block_filename_verdict(self, mock_env_helper, mock_openai_client):
        """Test that BLOCK_FILENAME verdict is treated as BLOCK (blocks content)."""
        mock_openai_client.chat.completions.create.return_value.choices[0].message.content = "BLOCK_FILENAME"
        validator = RAIValidator(mock_env_helper)
        validator.client = mock_openai_client

        is_valid, message = validator.validate_content("FILENAME: malware.exe")

        assert is_valid is False
        assert "inappropriate" in message.lower()

    def test_validate_content_blocks_on_block_both_verdict(self, mock_env_helper, mock_openai_client):
        """Test blocking with BLOCK_BOTH verdict (treated as BLOCK)."""
        mock_openai_client.chat.completions.create.return_value.choices[0].message.content = "BLOCK_BOTH"
        validator = RAIValidator(mock_env_helper)
        validator.client = mock_openai_client

        is_valid, message = validator.validate_content("FILENAME: bad.txt\nCONTENT: harmful")

        assert is_valid is False
        assert "inappropriate" in message.lower()

    def test_validate_content_blocks_on_unclear_verdict(self, mock_env_helper, mock_openai_client):
        """Test that unclear verdict defaults to blocking."""
        mock_openai_client.chat.completions.create.return_value.choices[0].message.content = "UNCLEAR_RESPONSE"
        validator = RAIValidator(mock_env_helper)
        validator.client = mock_openai_client

        is_valid, message = validator.validate_content("Some content")

        assert is_valid is False
        assert "could not be verified" in message.lower()

    def test_validate_content_handles_empty_content(self, mock_env_helper):
        """Test that empty content is allowed without API call."""
        validator = RAIValidator(mock_env_helper)

        is_valid, message = validator.validate_content("")

        assert is_valid is True
        assert message == ""

    def test_validate_content_handles_whitespace_only(self, mock_env_helper):
        """Test that whitespace-only content is allowed without API call."""
        validator = RAIValidator(mock_env_helper)

        is_valid, message = validator.validate_content("   \n\t  ")

        assert is_valid is True
        assert message == ""

    def test_validate_content_truncates_long_content(self, mock_env_helper, mock_openai_client):
        """Test that long content is truncated to max_chars."""
        validator = RAIValidator(mock_env_helper)
        validator.client = mock_openai_client
        long_content = "A" * 15000

        is_valid, _ = validator.validate_content(long_content, max_chars=10000)

        assert is_valid is True
        # Verify the call was made with truncated content
        call_args = mock_openai_client.chat.completions.create.call_args
        user_message = call_args[1]["messages"][1]["content"]
        assert len(user_message) == 10000

    def test_validate_content_blocks_when_client_not_initialized(self, mock_env_helper):
        """Test that validation blocks when OpenAI client is not available."""
        validator = RAIValidator(mock_env_helper)
        validator.client = None

        is_valid, message = validator.validate_content("Some content")

        assert is_valid is False
        assert "validation service not available" in message.lower()

    def test_validate_content_handles_api_exception(self, mock_env_helper, mock_openai_client):
        """Test that API exceptions are handled gracefully."""
        mock_openai_client.chat.completions.create.side_effect = Exception("API Error")
        validator = RAIValidator(mock_env_helper)
        validator.client = mock_openai_client

        is_valid, message = validator.validate_content("Some content")

        assert is_valid is False
        assert "unable to validate" in message.lower()

    def test_validate_content_uses_custom_deployment_name(self, mock_env_helper, mock_openai_client):
        """Test that custom RAI deployment name is used if configured."""
        mock_env_helper.AZURE_OPENAI_RAI_DEPLOYMENT_NAME = "custom-rai-model"
        validator = RAIValidator(mock_env_helper)
        validator.client = mock_openai_client

        validator.validate_content("Test content")

        call_args = mock_openai_client.chat.completions.create.call_args
        assert call_args[1]["model"] == "custom-rai-model"

    def test_validate_content_uses_system_prompt(self, mock_env_helper, mock_openai_client):
        """Test that system prompt is included in API call."""
        validator = RAIValidator(mock_env_helper)
        validator.client = mock_openai_client

        validator.validate_content("Test content")

        call_args = mock_openai_client.chat.completions.create.call_args
        messages = call_args[1]["messages"]
        assert messages[0]["role"] == "system"
        assert "content safety validator" in messages[0]["content"]


class TestValidateFileContent:
    """Test file content validation functionality."""

    def test_validate_file_content_allows_safe_file(self, mock_env_helper, mock_openai_client):
        """Test that safe file is allowed."""
        validator = RAIValidator(mock_env_helper)
        validator.client = mock_openai_client
        file_content = b"This is safe educational content."

        is_valid, message = validator.validate_file_content(file_content, "document.txt")

        assert is_valid is True
        assert message == ""

    def test_validate_file_content_blocks_empty_filename(self, mock_env_helper):
        """Test that empty filename is blocked."""
        validator = RAIValidator(mock_env_helper)

        is_valid, message = validator.validate_file_content(b"content", "")

        assert is_valid is False
        assert "filename cannot be empty" in message.lower()

    def test_validate_file_content_blocks_whitespace_filename(self, mock_env_helper):
        """Test that whitespace-only filename is blocked."""
        validator = RAIValidator(mock_env_helper)

        is_valid, message = validator.validate_file_content(b"content", "   ")

        assert is_valid is False
        assert "filename cannot be empty" in message.lower()

    def test_validate_file_content_blocks_large_file(self, mock_env_helper):
        """Test that files larger than 50MB are blocked."""
        validator = RAIValidator(mock_env_helper)
        large_content = b"X" * (51 * 1024 * 1024)  # 51 MB

        is_valid, message = validator.validate_file_content(large_content, "large.txt")

        assert is_valid is False
        assert "file too large" in message.lower()
        assert "50mb" in message.lower()

    def test_validate_file_content_blocks_empty_file(self, mock_env_helper):
        """Test that empty files (0 bytes) are blocked."""
        validator = RAIValidator(mock_env_helper)

        is_valid, message = validator.validate_file_content(b"", "empty.txt")

        assert is_valid is False
        assert "file is empty" in message.lower()

    def test_validate_file_content_handles_utf8_encoding(self, mock_env_helper, mock_openai_client):
        """Test successful UTF-8 decoding."""
        validator = RAIValidator(mock_env_helper)
        validator.client = mock_openai_client
        utf8_content = "Test content with UTF-8 characters: é, ñ, ü".encode("utf-8")

        is_valid, _ = validator.validate_file_content(utf8_content, "test.txt")

        assert is_valid is True

    def test_validate_file_content_handles_latin1_encoding(self, mock_env_helper, mock_openai_client):
        """Test fallback to latin-1 encoding when UTF-8 fails."""
        validator = RAIValidator(mock_env_helper)
        validator.client = mock_openai_client
        # Create content that's valid latin-1 but invalid UTF-8
        latin1_content = bytes([0xE9, 0xF1, 0xFC])  # é, ñ, ü in latin-1

        is_valid, _ = validator.validate_file_content(latin1_content, "test.txt")

        assert is_valid is True

    def test_validate_file_content_handles_binary_safe_filename(self, mock_env_helper, mock_openai_client):
        """Test that binary files with safe filenames are allowed."""
        validator = RAIValidator(mock_env_helper)
        validator.client = mock_openai_client
        binary_content = bytes([0xFF, 0xD8, 0xFF, 0xE0])  # JPEG header

        is_valid, message = validator.validate_file_content(binary_content, "image.jpg")

        assert is_valid is True
        assert message == ""

    def test_validate_file_content_allows_binary_suspicious_filename_bomb(self, mock_env_helper, mock_openai_client):
        """Test that binary files with suspicious filenames are allowed (Scenario 2: harmful name + safe content)."""
        validator = RAIValidator(mock_env_helper)
        validator.client = mock_openai_client
        binary_content = bytes([0xFF, 0xD8, 0xFF, 0xE0])  # JPEG header

        is_valid, message = validator.validate_file_content(binary_content, "how_to_make_bomb.bin")

        assert is_valid is True
        assert message == ""

    def test_validate_file_content_allows_binary_suspicious_filename_weapon(self, mock_env_helper, mock_openai_client):
        """Test that binary files with 'weapon' in filename are allowed (Scenario 2)."""
        validator = RAIValidator(mock_env_helper)
        validator.client = mock_openai_client
        binary_content = bytes([0xFF, 0xD8, 0xFF, 0xE0])  # JPEG header

        is_valid, message = validator.validate_file_content(binary_content, "weapon_guide.dat")

        assert is_valid is True
        assert message == ""

    def test_validate_file_content_allows_binary_suspicious_filename_malware(self, mock_env_helper, mock_openai_client):
        """Test that binary files with 'malware' in filename are allowed (Scenario 2)."""
        validator = RAIValidator(mock_env_helper)
        validator.client = mock_openai_client
        binary_content = bytes([0xFF, 0xD8, 0xFF, 0xE0])  # JPEG header

        is_valid, message = validator.validate_file_content(binary_content, "malware.exe")

        assert is_valid is True
        assert message == ""

    def test_validate_file_content_truncates_long_content(self, mock_env_helper, mock_openai_client):
        """Test that long file content is truncated."""
        validator = RAIValidator(mock_env_helper)
        validator.client = mock_openai_client
        long_content = ("A" * 15000).encode("utf-8")

        is_valid, _ = validator.validate_file_content(long_content, "test.txt", max_chars=5000)

        assert is_valid is True

    def test_validate_file_content_combines_filename_and_content(self, mock_env_helper, mock_openai_client):
        """Test that filename and content are combined in single API call."""
        validator = RAIValidator(mock_env_helper)
        validator.client = mock_openai_client

        validator.validate_file_content(b"Test content", "test.txt")

        call_args = mock_openai_client.chat.completions.create.call_args
        user_message = call_args[1]["messages"][1]["content"]
        assert "FILENAME: test.txt" in user_message
        assert "CONTENT:" in user_message
        assert "Test content" in user_message

    def test_validate_file_content_handles_validation_exception(self, mock_env_helper, mock_openai_client):
        """Test exception handling during file validation."""
        validator = RAIValidator(mock_env_helper)
        validator.client = mock_openai_client

        # Mock validate_content to raise an exception
        with patch.object(validator, 'validate_content', side_effect=Exception("Validation error")):
            is_valid, message = validator.validate_file_content(b"Test", "test.txt")

        assert is_valid is False
        assert "unable to validate" in message.lower()

    def test_validate_file_content_propagates_block_verdict(self, mock_env_helper, mock_openai_client):
        """Test that BLOCK verdict from validate_content is propagated."""
        mock_openai_client.chat.completions.create.return_value.choices[0].message.content = "BLOCK_CONTENT"
        validator = RAIValidator(mock_env_helper)
        validator.client = mock_openai_client

        is_valid, message = validator.validate_file_content(b"Harmful content", "test.txt")

        assert is_valid is False
        assert "inappropriate" in message.lower()


class TestSingletonPattern:
    """Test singleton pattern implementation."""

    def test_get_rai_validator_returns_same_instance(self):
        """Test that get_rai_validator returns the same instance."""
        with patch("backend.batch.utilities.helpers.rai_validator.AzureOpenAI"):
            validator1 = get_rai_validator()
            validator2 = get_rai_validator()

            assert validator1 is validator2

    def test_singleton_get_instance_creates_on_first_call(self):
        """Test that singleton creates instance on first call."""
        with patch("backend.batch.utilities.helpers.rai_validator.AzureOpenAI"):
            assert _RAIValidatorSingleton._instance is None

            validator = _RAIValidatorSingleton.get_instance()

            assert validator is not None
            assert _RAIValidatorSingleton._instance is validator

    def test_singleton_get_instance_reuses_existing(self):
        """Test that singleton reuses existing instance."""
        with patch("backend.batch.utilities.helpers.rai_validator.AzureOpenAI"):
            validator1 = _RAIValidatorSingleton.get_instance()
            validator2 = _RAIValidatorSingleton.get_instance()

            assert validator1 is validator2


class TestConvenienceFunctions:
    """Test convenience wrapper functions."""

    def test_validate_content_function_uses_singleton(self):
        """Test that validate_content function uses global singleton."""
        with patch("backend.batch.utilities.helpers.rai_validator.AzureOpenAI"):
            with patch.object(_RAIValidatorSingleton, 'get_instance') as mock_get:
                mock_validator = Mock()
                mock_validator.validate_content.return_value = (True, "")
                mock_get.return_value = mock_validator

                is_valid, _ = validate_content("Test content")

                mock_validator.validate_content.assert_called_once_with("Test content")
                assert is_valid is True

    def test_validate_file_content_function_uses_singleton(self):
        """Test that validate_file_content function uses global singleton."""
        with patch("backend.batch.utilities.helpers.rai_validator.AzureOpenAI"):
            with patch.object(_RAIValidatorSingleton, 'get_instance') as mock_get:
                mock_validator = Mock()
                mock_validator.validate_file_content.return_value = (True, "")
                mock_get.return_value = mock_validator

                is_valid, _ = validate_file_content(b"Test", "test.txt")

                mock_validator.validate_file_content.assert_called_once_with(b"Test", "test.txt")
                assert is_valid is True


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_validate_content_with_special_characters(self, mock_env_helper, mock_openai_client):
        """Test content with special characters."""
        validator = RAIValidator(mock_env_helper)
        validator.client = mock_openai_client
        special_content = "Content with special chars: @#$%^&*()_+-=[]{}|;:',.<>?/~`"

        is_valid, _ = validator.validate_content(special_content)

        assert is_valid is True

    def test_validate_content_with_unicode_emoji(self, mock_env_helper, mock_openai_client):
        """Test content with unicode emoji characters."""
        validator = RAIValidator(mock_env_helper)
        validator.client = mock_openai_client
        emoji_content = "Hello 👋 World 🌍 with emoji 😀"

        is_valid, _ = validator.validate_content(emoji_content)

        assert is_valid is True

    def test_validate_file_content_at_size_boundary(self, mock_env_helper, mock_openai_client):
        """Test file at exact 50MB boundary."""
        validator = RAIValidator(mock_env_helper)
        validator.client = mock_openai_client
        boundary_content = b"X" * (50 * 1024 * 1024)  # Exactly 50 MB

        is_valid, _ = validator.validate_file_content(boundary_content, "boundary.txt")

        # Should be allowed as it's not > 50MB
        assert is_valid is True

    def test_validate_content_verdict_case_insensitivity(self, mock_env_helper, mock_openai_client):
        """Test that verdict parsing is case-insensitive."""
        mock_openai_client.chat.completions.create.return_value.choices[0].message.content = "allow"
        validator = RAIValidator(mock_env_helper)
        validator.client = mock_openai_client

        is_valid, _ = validator.validate_content("Test")

        assert is_valid is True

    def test_validate_file_content_allows_suspicious_patterns_case_insensitive(self, mock_env_helper, mock_openai_client):
        """Test that binary files with suspicious filenames are allowed regardless of case (Scenario 2)."""
        validator = RAIValidator(mock_env_helper)
        validator.client = mock_openai_client
        binary_content = bytes([0xFF, 0xD8])

        is_valid, message = validator.validate_file_content(binary_content, "WEAPON_Guide.bin")

        assert is_valid is True
        assert message == ""

    def test_validate_content_with_max_chars_zero(self, mock_env_helper, mock_openai_client):
        """Test validation with max_chars set to 0."""
        validator = RAIValidator(mock_env_helper)
        validator.client = mock_openai_client

        _, _ = validator.validate_content("Some content", max_chars=0)

        # Should still call API with empty content
        call_args = mock_openai_client.chat.completions.create.call_args
        user_message = call_args[1]["messages"][1]["content"]
        assert user_message == ""

    def test_validate_file_all_suspicious_patterns(self, mock_env_helper, mock_openai_client):
        """Test all suspicious filenames are allowed when content is binary/safe (Scenario 2)."""
        validator = RAIValidator(mock_env_helper)
        validator.client = mock_openai_client
        binary_content = bytes([0xFF, 0xD8])

        suspicious_filenames = [
            "bomb_guide.bin",
            "weapon_manual.dat",
            "exploit_tool.exe",
            "malware_sample.bin",
            "virus_code.dat",
            "hack_tutorial.exe"
        ]

        for filename in suspicious_filenames:
            is_valid, message = validator.validate_file_content(binary_content, filename)
            assert is_valid is True, f"Should allow binary file: {filename}"
            assert message == ""

    def test_validate_binary_file_truly_undecodable_safe_filename(self, mock_env_helper):
        """Test binary files that can't be decoded with safe filenames pass through."""
        validator = RAIValidator(mock_env_helper)

        # Mock the validate_file_content's decode attempts to properly simulate binary
        with patch('backend.batch.utilities.helpers.rai_validator.logger'):
            # Create a custom bytes object that raises on decode
            class UndecodableBytes(bytes):
                def decode(self, *args, **kwargs):
                    raise UnicodeDecodeError('utf-8', b'', 0, 1, 'cannot decode')

            binary_content = UndecodableBytes([0x89, 0x50, 0x4E, 0x47])  # PNG header
            is_valid, message = validator.validate_file_content(binary_content, "image.png")

            # Should be allowed - safe filename, truly binary
            assert is_valid is True
            assert message == ""

    def test_validate_binary_file_undecodable_suspicious_filename(self, mock_env_helper):
        """Test binary files that can't be decoded with suspicious filenames are allowed (Scenario 2)."""
        validator = RAIValidator(mock_env_helper)

        with patch('backend.batch.utilities.helpers.rai_validator.logger'):
            # Create a custom bytes object that raises on decode
            class UndecodableBytes(bytes):
                def decode(self, *args, **kwargs):
                    raise UnicodeDecodeError('utf-8', b'', 0, 1, 'cannot decode')

            binary_content = UndecodableBytes([0x89, 0x50, 0x4E, 0x47])  # PNG header
            is_valid, message = validator.validate_file_content(binary_content, "bomb_instructions.bin")

            # Should be allowed - Scenario 2: harmful filename but no harmful content
            assert is_valid is True
            assert message == ""
