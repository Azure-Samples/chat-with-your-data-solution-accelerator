"""Tests for src/functions/core/telemetry.py."""

import pytest

from functions.core.telemetry import configure_telemetry


def test_configure_telemetry_noop_without_connection_string(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No APPLICATIONINSIGHTS_CONNECTION_STRING -> telemetry stays off:
    configure_azure_monitor is never called and the helper returns False."""
    monkeypatch.delenv("APPLICATIONINSIGHTS_CONNECTION_STRING", raising=False)
    calls: list[str] = []
    monkeypatch.setattr(
        "functions.core.telemetry.configure_azure_monitor",
        lambda **kw: calls.append(kw["connection_string"]),
    )
    assert configure_telemetry() is False
    assert calls == []


def test_configure_telemetry_configures_when_connection_string_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The Functions host provides APPLICATIONINSIGHTS_CONNECTION_STRING;
    when set, the worker configures Azure Monitor with that value."""
    conn = (
        "InstrumentationKey=00000000-0000-0000-0000-000000000000;"
        "IngestionEndpoint=https://uksouth.in.applicationinsights.azure.com/"
    )
    monkeypatch.setenv("APPLICATIONINSIGHTS_CONNECTION_STRING", conn)
    captured: dict[str, str] = {}
    monkeypatch.setattr(
        "functions.core.telemetry.configure_azure_monitor",
        lambda **kw: captured.update(kw),
    )
    assert configure_telemetry() is True
    assert captured["connection_string"] == conn
