"""
Pillar: Stable Core
Phase: 3 (Conversation + RAG, task #26)
Purpose: Validate post_provision.py search-index bootstrap and CLI flags.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

# The script lives in v2/scripts/, which is not on pythonpath. Load it
# directly with importlib so tests don't depend on PYTHONPATH munging.
_SCRIPT_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "post_provision.py"
)
_spec = importlib.util.spec_from_file_location("_post_provision", _SCRIPT_PATH)
assert _spec and _spec.loader
post_provision = importlib.util.module_from_spec(_spec)
sys.modules["_post_provision"] = post_provision
_spec.loader.exec_module(post_provision)


class _FakeNotFound(Exception):
    """Stand-in for azure.core.exceptions.ResourceNotFoundError.

    The production code matches by class name only, so any exception
    class literally named ``ResourceNotFoundError`` triggers create.
    """


_FakeNotFound.__name__ = "ResourceNotFoundError"


class _FakeSearchIndexClient:
    def __init__(self, *, exists: bool):
        self._exists = exists
        self.get_calls: list[str] = []
        self.created: list[object] = []
        self.closed = False

    def get_index(self, name: str):
        self.get_calls.append(name)
        if not self._exists:
            raise _FakeNotFound(f"no index {name}")
        return {"name": name}

    def create_index(self, index):
        self.created.append(index)

    def close(self):
        self.closed = True


def test_ensure_search_index_skips_when_endpoint_missing(monkeypatch, capsys):
    # AZURE_AI_SEARCH_ENDPOINT not set — postgresql-mode deploy.
    sentinel = {"called": False}

    def factory():
        sentinel["called"] = True
        raise AssertionError("client_factory should not be invoked")

    result = post_provision._ensure_search_index(
        dry_run=False, client_factory=factory
    )

    assert result == "skipped"
    assert sentinel["called"] is False
    assert "skipping search index" in capsys.readouterr().out


def test_ensure_search_index_dry_run_makes_no_calls(monkeypatch, capsys):
    monkeypatch.setenv("AZURE_AI_SEARCH_ENDPOINT", "https://srch.example/")

    def factory():
        raise AssertionError("dry-run must not build a client")

    result = post_provision._ensure_search_index(
        dry_run=True, client_factory=factory
    )

    out = capsys.readouterr().out
    assert result == "dry-run"
    assert "[dry-run]" in out
    assert "cwyd-index" in out


def test_ensure_search_index_idempotent_when_exists(monkeypatch):
    monkeypatch.setenv("AZURE_AI_SEARCH_ENDPOINT", "https://srch.example/")
    monkeypatch.setenv("AZURE_AI_SEARCH_INDEX", "custom-index")
    fake = _FakeSearchIndexClient(exists=True)

    result = post_provision._ensure_search_index(
        dry_run=False, client_factory=lambda: fake
    )

    assert result == "exists"
    assert fake.get_calls == ["custom-index"]
    assert fake.created == []
    assert fake.closed is True


def test_ensure_search_index_creates_when_missing(monkeypatch):
    monkeypatch.setenv("AZURE_AI_SEARCH_ENDPOINT", "https://srch.example/")
    monkeypatch.setenv("AZURE_OPENAI_EMBEDDING_DIMENSIONS", "768")
    fake = _FakeSearchIndexClient(exists=False)

    result = post_provision._ensure_search_index(
        dry_run=False, client_factory=lambda: fake
    )

    assert result == "created"
    assert len(fake.created) == 1
    created = fake.created[0]
    # SearchIndex object surface — name + a vector field of right dims.
    assert created.name == post_provision.DEFAULT_INDEX_NAME
    vector_field = next(f for f in created.fields if f.name == "content_vector")
    assert vector_field.vector_search_dimensions == 768
    field_names = {f.name for f in created.fields}
    assert {"id", "content", "title", "url", "content_vector"} <= field_names
    assert fake.closed is True


def test_ensure_search_index_propagates_unexpected_errors(monkeypatch):
    monkeypatch.setenv("AZURE_AI_SEARCH_ENDPOINT", "https://srch.example/")

    class _Boom(Exception):
        pass

    class _ExplodingClient(_FakeSearchIndexClient):
        def get_index(self, name: str):
            raise _Boom("auth failed")

    fake = _ExplodingClient(exists=False)
    with pytest.raises(_Boom):
        post_provision._ensure_search_index(
            dry_run=False, client_factory=lambda: fake
        )
    # close() still called from the finally block.
    assert fake.closed is True


def test_main_dry_run_cosmosdb_skips_postgres_and_search_calls(
    monkeypatch, capsys
):
    monkeypatch.setenv("AZURE_DB_TYPE", "cosmosdb")

    rc = post_provision.main(["--dry-run"])

    out = capsys.readouterr().out
    assert rc == 0
    assert "skipping postgres setup" in out
    # Search endpoint not set → skipped path.
    assert "skipping search index" in out
    assert "azd outputs" in out


def test_main_dry_run_postgresql_announces_pgvector(monkeypatch, capsys):
    monkeypatch.setenv("AZURE_DB_TYPE", "postgresql")
    rc = post_provision.main(["--dry-run"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "[dry-run] would enable pgvector extension" in out


def test_main_rejects_unknown_db_type(monkeypatch, capsys):
    monkeypatch.setenv("AZURE_DB_TYPE", "mongodb")
    rc = post_provision.main(["--dry-run"])
    err = capsys.readouterr().err
    assert rc == 6
    assert "AZURE_DB_TYPE" in err


def test_main_missing_required_env_exits_2(monkeypatch, capsys):
    # AZURE_DB_TYPE stripped by autouse _reset_env fixture.
    with pytest.raises(SystemExit) as excinfo:
        post_provision.main(["--dry-run"])
    assert excinfo.value.code == 2
    assert "AZURE_DB_TYPE" in capsys.readouterr().err


def test_ensure_search_index_rejects_bad_dimensions(monkeypatch):
    monkeypatch.setenv("AZURE_AI_SEARCH_ENDPOINT", "https://srch.example/")
    monkeypatch.setenv("AZURE_OPENAI_EMBEDDING_DIMENSIONS", "not-a-number")
    with pytest.raises(SystemExit) as excinfo:
        post_provision._ensure_search_index(dry_run=True, client_factory=lambda: None)
    assert excinfo.value.code == 8


# ---------------------------------------------------------------------------
# Agent registry bootstrap (CU-010b3 -- no-op closure)
# ---------------------------------------------------------------------------
#
# CU-010b3 deliberately makes NO change to post_provision.py. The agent
# registry is bootstrapped lazily by the per-backend client:
#   * Cosmos: reuses the chat-history container; agent rows just use
#     `userId="_system"` + `type=CosmosItemType.AGENT` (no DDL needed).
#   * Postgres: the `agents` table is part of `_SCHEMA_SQL` which runs
#     under `_ensure_pool()` on first DB call (idempotent CREATE TABLE
#     IF NOT EXISTS).
#
# These tests lock in that decision: a future regression that moves
# agent-table DDL or container creation into post_provision would break
# the lazy-bootstrap contract (and would force every `azd up` to take
# a write dependency on Postgres / Cosmos at provisioning time, which
# the dev loop should not require).


def test_post_provision_does_not_reference_agents_table() -> None:
    """post_provision.py must not contain DDL or references to the\n    `agents` table -- bootstrap stays in postgres.py `_SCHEMA_SQL`."""
    source = _SCRIPT_PATH.read_text(encoding="utf-8")
    assert "agents" not in source.lower().split()  # noqa: PLR2004
    # Tighter check: the verbs we'd see if someone moved DDL here.
    assert "CREATE TABLE" not in source
    assert "agent_id" not in source


def test_post_provision_does_not_reference_agent_partition() -> None:
    """post_provision.py must not pre-seed the `_system` partition or\n    write agent items -- the Cosmos client owns that wire shape."""
    source = _SCRIPT_PATH.read_text(encoding="utf-8")
    assert "_system" not in source
    assert "CosmosItemType" not in source
    assert "upsert_item" not in source
