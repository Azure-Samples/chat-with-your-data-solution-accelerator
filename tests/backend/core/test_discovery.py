"""Tests for backend.core.discovery."""

import logging
from importlib.metadata import EntryPoint
from unittest.mock import MagicMock, patch

import pytest

from backend.core.discovery import load_entry_points


def _make_fake_ep(name: str, value: str, load_side_effect: object = None) -> MagicMock:
    ep = MagicMock(spec=EntryPoint)
    ep.name = name
    ep.value = value
    ep.group = "cwyd.providers.test"
    if isinstance(load_side_effect, BaseException) or (
        isinstance(load_side_effect, type)
        and issubclass(load_side_effect, BaseException)
    ):
        ep.load.side_effect = load_side_effect
    else:
        ep.load.return_value = load_side_effect
    return ep


def _patch_entry_points(eps: list[MagicMock]):
    return patch("backend.core.discovery.entry_points", return_value=eps)


def test_load_entry_points_returns_zero_for_empty_group():
    with _patch_entry_points([]):
        assert load_entry_points("cwyd.providers.test") == 0


def test_load_entry_points_rejects_empty_group():
    with pytest.raises(ValueError) as exc:
        load_entry_points("")
    assert "non-empty" in str(exc.value)


def test_load_entry_points_invokes_ep_load_for_each_entry():
    ep = _make_fake_ep("fake", "cwyd_fake.client", load_side_effect=object())
    with _patch_entry_points([ep]):
        count = load_entry_points("cwyd.providers.test")
    assert count == 1
    ep.load.assert_called_once_with()


def test_load_entry_points_loads_multiple_plugins_in_order():
    ep_a = _make_fake_ep("a", "cwyd_a.client", load_side_effect=object())
    ep_b = _make_fake_ep("b", "cwyd_b.client", load_side_effect=object())
    with _patch_entry_points([ep_a, ep_b]):
        count = load_entry_points("cwyd.providers.test")
    assert count == 2
    ep_a.load.assert_called_once_with()
    ep_b.load.assert_called_once_with()


def test_load_entry_points_reraises_on_plugin_load_failure(
    caplog: pytest.LogCaptureFixture,
):
    ep_good = _make_fake_ep("good", "cwyd_good.client", load_side_effect=object())
    ep_bad = _make_fake_ep(
        "bad", "cwyd_bad.client", load_side_effect=RuntimeError("boom")
    )
    ep_after = _make_fake_ep("after", "cwyd_after.client", load_side_effect=object())
    with _patch_entry_points([ep_good, ep_bad, ep_after]):
        with caplog.at_level(logging.ERROR, logger="backend.core.discovery"):
            with pytest.raises(RuntimeError, match="boom"):
                load_entry_points("cwyd.providers.test")
    # First plugin loaded; bad raised; subsequent plugin never reached.
    ep_good.load.assert_called_once_with()
    ep_bad.load.assert_called_once_with()
    ep_after.load.assert_not_called()
    # Structured failure log fired.
    failure_records = [
        r
        for r in caplog.records
        if r.name == "backend.core.discovery" and r.levelno == logging.ERROR
    ]
    assert len(failure_records) == 1
    record = failure_records[0]
    assert getattr(record, "operation", None) == "load_entry_point"
    assert getattr(record, "group", None) == "cwyd.providers.test"
    assert getattr(record, "plugin_name", None) == "bad"
    assert getattr(record, "plugin_value", None) == "cwyd_bad.client"


def test_load_entry_points_emits_structured_info_log_on_success(
    caplog: pytest.LogCaptureFixture,
):
    ep = _make_fake_ep("fake", "cwyd_fake.client", load_side_effect=object())
    with _patch_entry_points([ep]):
        with caplog.at_level(logging.INFO, logger="backend.core.discovery"):
            load_entry_points("cwyd.providers.test")
    success_records = [
        r
        for r in caplog.records
        if r.name == "backend.core.discovery" and r.levelno == logging.INFO
    ]
    assert len(success_records) == 1
    record = success_records[0]
    assert getattr(record, "operation", None) == "load_entry_point"
    assert getattr(record, "group", None) == "cwyd.providers.test"
    assert getattr(record, "plugin_name", None) == "fake"
    assert getattr(record, "plugin_value", None) == "cwyd_fake.client"
