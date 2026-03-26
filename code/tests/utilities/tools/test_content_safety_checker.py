from unittest.mock import MagicMock, patch
import pytest
from azure.core.exceptions import HttpResponseError
from backend.batch.utilities.tools.content_safety_checker import ContentSafetyChecker
from backend.batch.utilities.common.answer import Answer


@pytest.mark.azure("This test requires Azure Content Safety configured")
def test_document_chunking_layout():
    cut = ContentSafetyChecker()

    safe_input = "This is a test"
    unsafe_input = "I hate short people, they are dumb"

    assert cut.validate_input_and_replace_if_harmful(safe_input) == safe_input
    assert cut.validate_output_and_replace_if_harmful(safe_input) == safe_input
    assert cut.validate_input_and_replace_if_harmful(unsafe_input) != unsafe_input
    assert cut.validate_output_and_replace_if_harmful(unsafe_input) != unsafe_input


@patch("backend.batch.utilities.tools.content_safety_checker.get_azure_credential")
@patch("backend.batch.utilities.tools.content_safety_checker.ContentSafetyClient")
@patch("backend.batch.utilities.tools.content_safety_checker.EnvHelper")
def test_init_with_rbac_authentication(env_helper_mock, client_mock, credential_mock):
    """Test initialization with RBAC authentication."""
    # Given
    env_helper = env_helper_mock.return_value
    env_helper.AZURE_AUTH_TYPE = "rbac"
    env_helper.AZURE_CONTENT_SAFETY_ENDPOINT = "https://test.endpoint"
    env_helper.MANAGED_IDENTITY_CLIENT_ID = "test-client-id"

    # When
    checker = ContentSafetyChecker()

    # Then
    credential_mock.assert_called_once_with("test-client-id")
    client_mock.assert_called_once_with(
        "https://test.endpoint", credential_mock.return_value
    )
    assert checker.content_safety_client == client_mock.return_value


@patch("backend.batch.utilities.tools.content_safety_checker.AzureKeyCredential")
@patch("backend.batch.utilities.tools.content_safety_checker.ContentSafetyClient")
@patch("backend.batch.utilities.tools.content_safety_checker.EnvHelper")
def test_init_with_key_authentication(
    env_helper_mock, client_mock, key_credential_mock
):
    """Test initialization with AzureKeyCredential authentication."""
    # Given
    env_helper = env_helper_mock.return_value
    env_helper.AZURE_AUTH_TYPE = "key"
    env_helper.AZURE_CONTENT_SAFETY_ENDPOINT = "https://test.endpoint"
    env_helper.AZURE_CONTENT_SAFETY_KEY = "test-key"

    # When
    checker = ContentSafetyChecker()

    # Then
    key_credential_mock.assert_called_once_with("test-key")
    client_mock.assert_called_once_with(
        "https://test.endpoint", key_credential_mock.return_value
    )
    assert checker.content_safety_client == client_mock.return_value


@patch("backend.batch.utilities.tools.content_safety_checker.AzureKeyCredential")
@patch("backend.batch.utilities.tools.content_safety_checker.ContentSafetyClient")
@patch("backend.batch.utilities.tools.content_safety_checker.EnvHelper")
def test_process_answer_replaces_harmful_content(
    env_helper_mock, client_mock, key_credential_mock
):
    """Test process_answer filters and replaces harmful text."""
    # Given
    env_helper = env_helper_mock.return_value
    env_helper.AZURE_AUTH_TYPE = "key"
    env_helper.AZURE_CONTENT_SAFETY_ENDPOINT = "https://test.endpoint"
    env_helper.AZURE_CONTENT_SAFETY_KEY = "test-key"

    checker = ContentSafetyChecker()

    # Mock content safety response with harmful content detected
    mock_response = MagicMock()
    mock_category = MagicMock()
    mock_category.severity = 2  # Harmful content
    mock_response.categories_analysis = [mock_category]

    checker.content_safety_client.analyze_text = MagicMock(return_value=mock_response)

    answer = Answer(
        question="test",
        answer="harmful text",
        source_documents=[],
        prompt_tokens=10,
        completion_tokens=20,
    )
    response_template = "Content blocked"

    # When
    result = checker.process_answer(answer, response_template=response_template)

    # Then
    assert result.answer == "Content blocked"
    checker.content_safety_client.analyze_text.assert_called_once()


@patch("backend.batch.utilities.tools.content_safety_checker.AzureKeyCredential")
@patch("backend.batch.utilities.tools.content_safety_checker.ContentSafetyClient")
@patch("backend.batch.utilities.tools.content_safety_checker.EnvHelper")
def test_validate_input_and_replace_if_harmful_with_safe_text(
    env_helper_mock, client_mock, key_credential_mock
):
    """Test validate_input_and_replace_if_harmful with safe text."""
    # Given
    env_helper = env_helper_mock.return_value
    env_helper.AZURE_AUTH_TYPE = "key"
    env_helper.AZURE_CONTENT_SAFETY_ENDPOINT = "https://test.endpoint"
    env_helper.AZURE_CONTENT_SAFETY_KEY = "test-key"

    checker = ContentSafetyChecker()

    # Mock content safety response with no harmful content
    mock_response = MagicMock()
    mock_category = MagicMock()
    mock_category.severity = 0  # Safe content
    mock_response.categories_analysis = [mock_category]

    checker.content_safety_client.analyze_text = MagicMock(return_value=mock_response)

    # When
    result = checker.validate_input_and_replace_if_harmful("safe text")

    # Then
    assert result == "safe text"


@patch("backend.batch.utilities.tools.content_safety_checker.AzureKeyCredential")
@patch("backend.batch.utilities.tools.content_safety_checker.ContentSafetyClient")
@patch("backend.batch.utilities.tools.content_safety_checker.EnvHelper")
def test_validate_input_and_replace_if_harmful_with_harmful_text(
    env_helper_mock, client_mock, key_credential_mock
):
    """Test validate_input_and_replace_if_harmful with harmful text."""
    # Given
    env_helper = env_helper_mock.return_value
    env_helper.AZURE_AUTH_TYPE = "key"
    env_helper.AZURE_CONTENT_SAFETY_ENDPOINT = "https://test.endpoint"
    env_helper.AZURE_CONTENT_SAFETY_KEY = "test-key"

    checker = ContentSafetyChecker()

    # Mock content safety response with harmful content detected
    mock_response = MagicMock()
    mock_category = MagicMock()
    mock_category.severity = 2  # Harmful content
    mock_response.categories_analysis = [mock_category]

    checker.content_safety_client.analyze_text = MagicMock(return_value=mock_response)

    # When
    result = checker.validate_input_and_replace_if_harmful("harmful text")

    # Then
    assert "Unfortunately, I am not able to process your question" in result
    assert result != "harmful text"


@patch("backend.batch.utilities.tools.content_safety_checker.AzureKeyCredential")
@patch("backend.batch.utilities.tools.content_safety_checker.ContentSafetyClient")
@patch("backend.batch.utilities.tools.content_safety_checker.EnvHelper")
def test_validate_output_and_replace_if_harmful_with_safe_text(
    env_helper_mock, client_mock, key_credential_mock
):
    """Test validate_output_and_replace_if_harmful with safe text."""
    # Given
    env_helper = env_helper_mock.return_value
    env_helper.AZURE_AUTH_TYPE = "key"
    env_helper.AZURE_CONTENT_SAFETY_ENDPOINT = "https://test.endpoint"
    env_helper.AZURE_CONTENT_SAFETY_KEY = "test-key"

    checker = ContentSafetyChecker()

    # Mock content safety response with no harmful content
    mock_response = MagicMock()
    mock_category = MagicMock()
    mock_category.severity = 0  # Safe content
    mock_response.categories_analysis = [mock_category]

    checker.content_safety_client.analyze_text = MagicMock(return_value=mock_response)

    # When
    result = checker.validate_output_and_replace_if_harmful("safe output")

    # Then
    assert result == "safe output"


@patch("backend.batch.utilities.tools.content_safety_checker.AzureKeyCredential")
@patch("backend.batch.utilities.tools.content_safety_checker.ContentSafetyClient")
@patch("backend.batch.utilities.tools.content_safety_checker.EnvHelper")
def test_validate_output_and_replace_if_harmful_with_harmful_text(
    env_helper_mock, client_mock, key_credential_mock
):
    """Test validate_output_and_replace_if_harmful with harmful text."""
    # Given
    env_helper = env_helper_mock.return_value
    env_helper.AZURE_AUTH_TYPE = "key"
    env_helper.AZURE_CONTENT_SAFETY_ENDPOINT = "https://test.endpoint"
    env_helper.AZURE_CONTENT_SAFETY_KEY = "test-key"

    checker = ContentSafetyChecker()

    # Mock content safety response with harmful content detected
    mock_response = MagicMock()
    mock_category = MagicMock()
    mock_category.severity = 3  # Harmful content
    mock_response.categories_analysis = [mock_category]

    checker.content_safety_client.analyze_text = MagicMock(return_value=mock_response)

    # When
    result = checker.validate_output_and_replace_if_harmful("harmful output")

    # Then
    assert "Unfortunately, I have detected sensitive content in my answer" in result
    assert result != "harmful output"


@patch("backend.batch.utilities.tools.content_safety_checker.AzureKeyCredential")
@patch("backend.batch.utilities.tools.content_safety_checker.ContentSafetyClient")
@patch("backend.batch.utilities.tools.content_safety_checker.EnvHelper")
def test_filter_text_and_replace_with_safe_content(env_helper_mock, client_mock, key_credential_mock):
    """Test _filter_text_and_replace returns original text when safe."""
    # Given
    env_helper = env_helper_mock.return_value
    env_helper.AZURE_AUTH_TYPE = "key"
    env_helper.AZURE_CONTENT_SAFETY_ENDPOINT = "https://test.endpoint"
    env_helper.AZURE_CONTENT_SAFETY_KEY = "test-key"

    checker = ContentSafetyChecker()

    # Mock content safety response with all categories safe
    mock_response = MagicMock()
    mock_category1 = MagicMock()
    mock_category1.severity = 0
    mock_category2 = MagicMock()
    mock_category2.severity = 0
    mock_response.categories_analysis = [mock_category1, mock_category2]

    checker.content_safety_client.analyze_text = MagicMock(return_value=mock_response)

    # When
    result = checker._filter_text_and_replace("safe text", "blocked")

    # Then
    assert result == "safe text"


@patch("backend.batch.utilities.tools.content_safety_checker.AzureKeyCredential")
@patch("backend.batch.utilities.tools.content_safety_checker.ContentSafetyClient")
@patch("backend.batch.utilities.tools.content_safety_checker.EnvHelper")
def test_filter_text_and_replace_with_harmful_content(env_helper_mock, client_mock, key_credential_mock):
    """Test _filter_text_and_replace replaces text when harmful content detected."""
    # Given
    env_helper = env_helper_mock.return_value
    env_helper.AZURE_AUTH_TYPE = "key"
    env_helper.AZURE_CONTENT_SAFETY_ENDPOINT = "https://test.endpoint"
    env_helper.AZURE_CONTENT_SAFETY_KEY = "test-key"

    checker = ContentSafetyChecker()

    # Mock content safety response with one harmful category
    mock_response = MagicMock()
    mock_category1 = MagicMock()
    mock_category1.severity = 0
    mock_category2 = MagicMock()
    mock_category2.severity = 4  # Harmful
    mock_response.categories_analysis = [mock_category1, mock_category2]

    checker.content_safety_client.analyze_text = MagicMock(return_value=mock_response)

    # When
    result = checker._filter_text_and_replace("harmful text", "Content blocked")

    # Then
    assert result == "Content blocked"


@patch("backend.batch.utilities.tools.content_safety_checker.AzureKeyCredential")
@patch("backend.batch.utilities.tools.content_safety_checker.ContentSafetyClient")
@patch("backend.batch.utilities.tools.content_safety_checker.EnvHelper")
def test_filter_text_and_replace_with_http_error_with_error_details(
    env_helper_mock, client_mock, key_credential_mock
):
    """Test _filter_text_and_replace raises exception on HttpResponseError with error details."""
    # Given
    env_helper = env_helper_mock.return_value
    env_helper.AZURE_AUTH_TYPE = "key"
    env_helper.AZURE_CONTENT_SAFETY_ENDPOINT = "https://test.endpoint"
    env_helper.AZURE_CONTENT_SAFETY_KEY = "test-key"

    checker = ContentSafetyChecker()

    # Mock HttpResponseError with error details
    error = MagicMock()
    error.code = "InvalidRequest"
    error.message = "Invalid text format"
    http_error = HttpResponseError(message="HTTP error")
    http_error.error = error

    checker.content_safety_client.analyze_text = MagicMock(side_effect=http_error)

    # When/Then
    with pytest.raises(HttpResponseError):
        checker._filter_text_and_replace("test", "blocked")


@patch("backend.batch.utilities.tools.content_safety_checker.AzureKeyCredential")
@patch("backend.batch.utilities.tools.content_safety_checker.ContentSafetyClient")
@patch("backend.batch.utilities.tools.content_safety_checker.EnvHelper")
def test_filter_text_and_replace_with_http_error_without_error_details(
    env_helper_mock, client_mock, key_credential_mock
):
    """Test _filter_text_and_replace raises exception on HttpResponseError without error details."""
    # Given
    env_helper = env_helper_mock.return_value
    env_helper.AZURE_AUTH_TYPE = "key"
    env_helper.AZURE_CONTENT_SAFETY_ENDPOINT = "https://test.endpoint"
    env_helper.AZURE_CONTENT_SAFETY_KEY = "test-key"

    checker = ContentSafetyChecker()

    # Mock HttpResponseError without error details
    http_error = HttpResponseError(message="HTTP error")
    http_error.error = None

    checker.content_safety_client.analyze_text = MagicMock(side_effect=http_error)

    # When/Then
    with pytest.raises(HttpResponseError):
        checker._filter_text_and_replace("test", "blocked")


@patch("backend.batch.utilities.tools.content_safety_checker.AzureKeyCredential")
@patch("backend.batch.utilities.tools.content_safety_checker.ContentSafetyClient")
@patch("backend.batch.utilities.tools.content_safety_checker.EnvHelper")
def test_filter_text_and_replace_checks_all_categories(env_helper_mock, client_mock, key_credential_mock):
    """Test _filter_text_and_replace checks all categories and replaces on first harmful."""
    # Given
    env_helper = env_helper_mock.return_value
    env_helper.AZURE_AUTH_TYPE = "key"
    env_helper.AZURE_CONTENT_SAFETY_ENDPOINT = "https://test.endpoint"
    env_helper.AZURE_CONTENT_SAFETY_KEY = "test-key"

    checker = ContentSafetyChecker()

    # Mock content safety response with multiple categories, second one harmful
    mock_response = MagicMock()
    categories = []
    for i in range(4):
        cat = MagicMock()
        cat.severity = 2 if i == 1 else 0  # Second category is harmful
        categories.append(cat)
    mock_response.categories_analysis = categories

    checker.content_safety_client.analyze_text = MagicMock(return_value=mock_response)

    # When
    result = checker._filter_text_and_replace("text with issues", "Replacement text")

    # Then
    assert result == "Replacement text"
