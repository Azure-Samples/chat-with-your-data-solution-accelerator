"""Tests for the content safety guardrail (Phase 3 task #20a).

Pillar: Stable Core
Phase: 3
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from shared.tools.content_safety import (
    DEFAULT_SEVERITY_THRESHOLD,
    ContentSafetyGuard,
    ContentSafetyVerdict,
)


def _category_analysis(category: str, severity: int) -> SimpleNamespace:
    return SimpleNamespace(category=category, severity=severity)


def _make_client(*categories: SimpleNamespace) -> MagicMock:
    client = MagicMock()
    client.analyze_text = AsyncMock(
        return_value=SimpleNamespace(categories_analysis=list(categories))
    )
    return client


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_default_threshold_is_medium() -> None:
    assert DEFAULT_SEVERITY_THRESHOLD == 4


def test_constructor_rejects_negative_threshold() -> None:
    with pytest.raises(ValueError, match="severity_threshold"):
        ContentSafetyGuard(client=MagicMock(), severity_threshold=-1)


# ---------------------------------------------------------------------------
# screen() behavior
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_screen_returns_unflagged_for_empty_text() -> None:
    client = _make_client()
    guard = ContentSafetyGuard(client=client)
    verdict = await guard.screen("")
    assert verdict == ContentSafetyVerdict(flagged=False)
    client.analyze_text.assert_not_called()


@pytest.mark.asyncio
async def test_screen_returns_unflagged_for_whitespace_only() -> None:
    client = _make_client()
    guard = ContentSafetyGuard(client=client)
    verdict = await guard.screen("   \n\t  ")
    assert verdict.flagged is False
    client.analyze_text.assert_not_called()


@pytest.mark.asyncio
async def test_screen_returns_unflagged_when_all_severities_below_threshold() -> None:
    client = _make_client(
        _category_analysis("Hate", 0),
        _category_analysis("Violence", 2),
    )
    guard = ContentSafetyGuard(client=client)
    verdict = await guard.screen("hello world")
    assert verdict.flagged is False
    assert verdict.triggered == []
    assert verdict.categories == {"Hate": 0, "Violence": 2}


@pytest.mark.asyncio
async def test_screen_flags_when_any_category_meets_threshold() -> None:
    client = _make_client(
        _category_analysis("Hate", 6),
        _category_analysis("Violence", 0),
    )
    guard = ContentSafetyGuard(client=client)
    verdict = await guard.screen("threatening content")
    assert verdict.flagged is True
    assert verdict.triggered == ["Hate"]
    assert verdict.categories["Hate"] == 6


@pytest.mark.asyncio
async def test_screen_lists_all_triggered_categories() -> None:
    client = _make_client(
        _category_analysis("Hate", 4),
        _category_analysis("SelfHarm", 6),
        _category_analysis("Violence", 2),
    )
    guard = ContentSafetyGuard(client=client)
    verdict = await guard.screen("bad content")
    assert verdict.flagged is True
    assert set(verdict.triggered) == {"Hate", "SelfHarm"}


@pytest.mark.asyncio
async def test_screen_threshold_is_inclusive_lower_bound() -> None:
    """Severity == threshold trips the guard."""
    client = _make_client(_category_analysis("Hate", 4))
    guard = ContentSafetyGuard(client=client, severity_threshold=4)
    verdict = await guard.screen("borderline")
    assert verdict.flagged is True


@pytest.mark.asyncio
async def test_screen_custom_threshold_can_be_strict() -> None:
    client = _make_client(_category_analysis("Hate", 2))
    guard = ContentSafetyGuard(client=client, severity_threshold=2)
    verdict = await guard.screen("low-severity input")
    assert verdict.flagged is True


@pytest.mark.asyncio
async def test_screen_handles_none_severity_as_zero() -> None:
    client = _make_client(SimpleNamespace(category="Hate", severity=None))
    guard = ContentSafetyGuard(client=client)
    verdict = await guard.screen("ambiguous response")
    assert verdict.flagged is False
    assert verdict.categories["Hate"] == 0
