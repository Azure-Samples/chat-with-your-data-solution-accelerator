import pytest
from backend.batch.utilities.tools.content_safety_checker import ContentSafetyChecker


@pytest.mark.azure("This test requires Azure Content Safety configured")
def test_document_chunking_layout():
    cut = ContentSafetyChecker()

    safe_input = "This is a test"
    unsafe_input = "I hate short people, they are dumb"

    assert cut.validate_input_and_replace_if_harmful(safe_input) == safe_input
    assert cut.validate_output_and_replace_if_harmful(safe_input) == safe_input
    assert cut.validate_input_and_replace_if_harmful(unsafe_input) != unsafe_input
    assert cut.validate_output_and_replace_if_harmful(unsafe_input) != unsafe_input
