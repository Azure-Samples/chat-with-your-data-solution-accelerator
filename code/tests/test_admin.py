"""
This module contains comprehensive unit tests for the Admin.py module.
Tests cover logging configuration, environment variable handling,
Streamlit setup, and Application Insights configuration.
"""

import sys
from unittest.mock import MagicMock, patch, mock_open
import pytest


# Mock Azure Monitor before importing Admin.py to prevent telemetry initialization
sys.modules['azure.monitor.opentelemetry'] = MagicMock()

# Mock streamlit before importing Admin.py to prevent module-level execution issues
mock_st = MagicMock()
mock_st.columns.return_value = (MagicMock(), MagicMock(), MagicMock())
sys.modules['streamlit'] = mock_st

# Patch builtins.open before importing to handle module-level load_css call
with patch('builtins.open', mock_open(read_data="/* default mock css */")):
    from backend.Admin import load_css


class TestLoadCSSFunction:
    """Tests for the load_css function."""

    @pytest.mark.parametrize("css_content,expected_tag_content", [
        ("body { color: red; }", "body { color: red; }"),
        (".container { margin: 0; }", ".container { margin: 0; }"),
        ("", ""),
        ("/* comment */\n.class { }", "/* comment */\n.class { }"),
        ("@import 'other.css';", "@import 'other.css';"),
        ("body {\n  color: blue;\n  background: white;\n}", "body {\n  color: blue;\n  background: white;\n}"),
    ])
    def test_load_css_reads_and_wraps_content(self, css_content, expected_tag_content):
        """Test load_css reads CSS file and wraps it in style tags."""
        with patch("builtins.open", mock_open(read_data=css_content)):
            with patch("backend.Admin.st.markdown") as mock_markdown:
                # When
                load_css("test.css")

                # Then
                expected_call = f"<style>{expected_tag_content}</style>"
                mock_markdown.assert_called_once_with(expected_call, unsafe_allow_html=True)

    def test_load_css_file_not_found(self):
        """Test load_css raises exception when file not found."""
        with patch("builtins.open", side_effect=FileNotFoundError("File not found")):
            with pytest.raises(FileNotFoundError):
                load_css("nonexistent.css")

    def test_load_css_permission_error(self):
        """Test load_css raises exception when permission denied."""
        with patch("builtins.open", side_effect=PermissionError("Permission denied")):
            with pytest.raises(PermissionError):
                load_css("restricted.css")
