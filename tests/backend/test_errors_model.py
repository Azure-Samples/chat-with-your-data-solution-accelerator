"""Tests for the documentation-only OpenAPI error-envelope models."""

from backend.models.errors import ConflictErrorResponse, ErrorResponse


def test_error_response_detail_has_description() -> None:
    schema = ErrorResponse.model_json_schema()
    description = schema["properties"]["detail"]["description"]
    assert isinstance(description, str)
    assert description


def test_conflict_error_response_exposes_error_and_reason() -> None:
    properties = ConflictErrorResponse.model_json_schema()["properties"]
    assert "error" in properties
    assert "reason" in properties
    for field_name in ("error", "reason"):
        description = properties[field_name]["description"]
        assert isinstance(description, str)
        assert description
