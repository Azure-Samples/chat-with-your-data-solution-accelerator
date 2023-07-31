import pytest
from .ContentSafetyChecker import ContentSafetyChecker


def test_document_chunking_layout():
    
    cut = ContentSafetyChecker()
    
    safe_input = "This is a test"
    unsafe_input = "I hate short people, they are dumb"
    
    assert cut.validate_input_and_replace_if_harmful(safe_input) == safe_input
    assert cut.validate_output_and_replace_if_harmful(safe_input) == safe_input
    assert cut.validate_input_and_replace_if_harmful(unsafe_input) != unsafe_input
    assert cut.validate_output_and_replace_if_harmful(unsafe_input) != unsafe_input
    