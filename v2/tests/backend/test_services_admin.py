"""Tests for ``backend.services.admin``.

Pillar: Stable Core
Phase: 5 (admin surface helpers)
"""

from datetime import UTC, datetime

from backend.services.admin import host_only, utcnow_iso


def test_utcnow_iso_returns_iso8601_with_utc_offset() -> None:
    value = utcnow_iso()
    parsed = datetime.fromisoformat(value)
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == UTC.utcoffset(parsed)


def test_utcnow_iso_is_monotonic_non_decreasing() -> None:
    first = datetime.fromisoformat(utcnow_iso())
    second = datetime.fromisoformat(utcnow_iso())
    assert second >= first


def test_host_only_returns_empty_string_for_empty_input() -> None:
    assert host_only("") == ""


def test_host_only_extracts_netloc_from_full_url() -> None:
    assert (
        host_only("https://my-foundry.eastus.api.azureml.ms/projects/p1?x=1")
        == "my-foundry.eastus.api.azureml.ms"
    )


def test_host_only_strips_path_and_query() -> None:
    result = host_only("https://example.com/tenant/abc?token=secret")
    assert "/tenant/abc" not in result
    assert "token" not in result
    assert result == "example.com"
