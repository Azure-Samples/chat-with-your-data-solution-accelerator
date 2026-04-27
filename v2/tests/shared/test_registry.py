"""Tests for shared.registry.Registry. Pillar: Stable Core. Phase: 1."""
from __future__ import annotations

import pytest

from shared.registry import Registry


class _Provider:
    pass


class _OtherProvider:
    pass


def test_register_and_get_returns_value():
    reg: Registry[type] = Registry("widgets")
    reg.register("Foo")(_Provider)
    assert reg.get("Foo") is _Provider


def test_get_is_case_insensitive():
    reg: Registry[type] = Registry("widgets")
    reg.register("AzureSearch")(_Provider)
    assert reg.get("azuresearch") is _Provider
    assert reg.get("AZURESEARCH") is _Provider
    assert "azuresearch" in reg
    assert "AzureSearch" in reg


def test_decorator_returns_value_unchanged():
    reg: Registry[type] = Registry("widgets")
    decorated = reg.register("Foo")(_Provider)
    assert decorated is _Provider


def test_get_unknown_key_raises_keyerror_with_available_listed():
    reg: Registry[type] = Registry("embedders")
    reg.register("AzureSearch")(_Provider)
    reg.register("pgvector")(_OtherProvider)
    with pytest.raises(KeyError) as exc:
        reg.get("missing")
    msg = str(exc.value)
    assert "embedders" in msg
    assert "missing" in msg
    assert "azuresearch" in msg
    assert "pgvector" in msg


def test_get_unknown_with_empty_registry_says_none():
    reg: Registry[type] = Registry("widgets")
    with pytest.raises(KeyError, match="<none>"):
        reg.get("anything")


def test_double_register_same_value_is_idempotent():
    reg: Registry[type] = Registry("widgets")
    reg.register("Foo")(_Provider)
    reg.register("Foo")(_Provider)  # must not raise
    assert reg.get("Foo") is _Provider


def test_double_register_different_value_raises():
    reg: Registry[type] = Registry("widgets")
    reg.register("Foo")(_Provider)
    with pytest.raises(ValueError, match="already registered"):
        reg.register("Foo")(_OtherProvider)


def test_empty_domain_rejected():
    with pytest.raises(ValueError):
        Registry("")


def test_empty_key_rejected():
    reg: Registry[type] = Registry("widgets")
    with pytest.raises(ValueError):
        reg.register("")(_Provider)


def test_keys_returns_sorted_list():
    reg: Registry[type] = Registry("widgets")
    reg.register("Zeta")(_Provider)
    reg.register("Alpha")(_OtherProvider)
    assert reg.keys() == ["alpha", "zeta"]
    assert len(reg) == 2


def test_contains_rejects_non_strings():
    reg: Registry[type] = Registry("widgets")
    reg.register("Foo")(_Provider)
    assert 42 not in reg
    assert None not in reg
