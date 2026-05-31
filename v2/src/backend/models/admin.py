"""Admin router request/response models.

Pillar: Stable Core
Phase: 5 (admin surface request/response models)
"""

from pydantic import BaseModel, Field


class DeleteDocumentResponse(BaseModel):
    """Response shape for ``DELETE /api/admin/documents/{source}``."""

    deleted: int = Field(
        ...,
        description="Number of indexed chunks removed for the source.",
        ge=0,
    )


__all__ = ["DeleteDocumentResponse"]
