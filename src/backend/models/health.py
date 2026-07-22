"""Pydantic response models for health checks."""

from enum import StrEnum

from pydantic import BaseModel, Field


class CheckStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"


class OverallStatus(StrEnum):
    PASS = "pass"
    DEGRADED = "degraded"
    FAIL = "fail"


class DependencyCheck(BaseModel):
    """Result of a single dependency probe."""

    name: str = Field(
        description="Name of the probed dependency (e.g. search, database, openai)."
    )
    status: CheckStatus = Field(
        description=(
            "Probe outcome: pass, fail, or skip when the dependency is not "
            "configured."
        )
    )
    detail: str = Field(
        default="",
        description="Human-readable context for the result; empty on a clean pass.",
    )


class HealthResponse(BaseModel):
    """Aggregate health response for `GET /api/health`.

    `status` is `pass` only when every required check passes. A single
    optional check failing yields `degraded`. A required check failing
    yields `fail`.
    """

    status: OverallStatus = Field(
        description=(
            "Aggregate status: pass when every required check passes, degraded "
            "when only optional checks fail, fail when a required check fails."
        )
    )
    version: str = Field(
        default="v2", description="Backend application version identifier."
    )
    checks: list[DependencyCheck] = Field(
        default_factory=list[DependencyCheck],
        description="Per-dependency probe results that determined the aggregate status.",
    )


__all__ = ["CheckStatus", "DependencyCheck", "HealthResponse", "OverallStatus"]
