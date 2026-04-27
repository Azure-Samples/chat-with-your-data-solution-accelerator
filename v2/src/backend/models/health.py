"""Pydantic response models for health checks.

Pillar: Stable Core
Phase: 2
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

CheckStatus = Literal["pass", "fail", "skip"]
OverallStatus = Literal["pass", "degraded", "fail"]


class DependencyCheck(BaseModel):
    """Result of a single dependency probe."""

    name: str
    status: CheckStatus
    detail: str = ""


class HealthResponse(BaseModel):
    """Aggregate health response for `GET /api/health`.

    `status` is `pass` only when every required check passes. A single
    optional check failing yields `degraded`. A required check failing
    yields `fail`.
    """

    status: OverallStatus
    version: str = "v2"
    checks: list[DependencyCheck] = Field(default_factory=list)


__all__ = ["CheckStatus", "DependencyCheck", "HealthResponse", "OverallStatus"]
