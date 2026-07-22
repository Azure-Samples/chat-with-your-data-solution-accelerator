"""Tests for src/functions/batch_start/models.py."""

import pytest
from pydantic import ValidationError

from functions.batch_start.models import BatchStartRequest


def test_happy_path_builds_with_all_fields() -> None:
    req = BatchStartRequest(
        container_name="documents",
        prefix="2026/",
        force_reindex=True,
    )
    assert req.container_name == "documents"
    assert req.prefix == "2026/"
    assert req.force_reindex is True


def test_optional_fields_default() -> None:
    req = BatchStartRequest(container_name="documents")
    assert req.prefix is None
    assert req.force_reindex is False


def test_empty_container_name_rejected() -> None:
    with pytest.raises(ValidationError):
        BatchStartRequest(container_name="")


def test_extra_fields_forbidden() -> None:
    with pytest.raises(ValidationError):
        BatchStartRequest(container_name="documents", unknown="nope")  # type: ignore[call-arg]


def test_model_is_frozen() -> None:
    req = BatchStartRequest(container_name="documents")
    with pytest.raises(ValidationError):
        req.container_name = "other"  # type: ignore[misc]
