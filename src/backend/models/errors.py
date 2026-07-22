"""Documentation-only OpenAPI error-envelope models."""

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Standard error body returned when a request fails."""

    detail: str = Field(description="Human-readable error message.")


class ConflictErrorResponse(BaseModel):
    """Error body returned when a request conflicts with the current state."""

    error: str = Field(description="Human-readable conflict message.")
    reason: str = Field(description="Machine-readable conflict reason code.")


__all__ = ["ErrorResponse", "ConflictErrorResponse"]
