"""
Purpose: Validate post_provision.py search-index bootstrap and CLI flags.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

# The script lives in infra/scripts/, which is not on pythonpath. Load it
# directly with importlib so tests don't depend on PYTHONPATH munging.
_SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "infra"
    / "scripts"
    / "post-provision"
    / "post_provision.py"
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
    # AZURE_AI_SEARCH_ENDPOINT not set -- postgresql-mode deploy.
    sentinel = {"called": False}

    def factory():
        sentinel["called"] = True
        raise AssertionError("client_factory should not be invoked")

    result = post_provision._ensure_search_index(dry_run=False, client_factory=factory)

    assert result == "skipped"
    assert sentinel["called"] is False
    assert "skipping search index" in capsys.readouterr().out


def test_ensure_search_index_dry_run_makes_no_calls(monkeypatch, capsys):
    monkeypatch.setenv("AZURE_AI_SEARCH_ENDPOINT", "https://srch.example/")

    def factory():
        raise AssertionError("dry-run must not build a client")

    result = post_provision._ensure_search_index(dry_run=True, client_factory=factory)

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
    # SearchIndex object surface -- name + a vector field of right dims.
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
        post_provision._ensure_search_index(dry_run=False, client_factory=lambda: fake)
    # close() still called from the finally block.
    assert fake.closed is True


def test_build_knowledge_base_seed_shape():
    knowledge_source, knowledge_base = post_provision._build_knowledge_base_seed(
        knowledge_source_name="cwyd-index-ks",
        knowledge_base_name="cwyd-kb",
        index_name="cwyd-index",
        semantic_configuration_name="default",
        openai_resource_uri="https://ai.example/",
        query_planning_deployment="chat",
        query_planning_model_name="gpt-5.1",
    )

    # Knowledge source: a searchIndex kind wrapping the existing chat index,
    # pinning its semantic configuration for agentic retrieval and requesting
    # the friendly title / url / content fields as citation source data so
    # knowledge-base citations carry the filename + snippet, not only the raw
    # document key.
    assert knowledge_source["name"] == "cwyd-index-ks"
    assert knowledge_source["kind"] == "searchIndex"
    assert knowledge_source["searchIndexParameters"] == {
        "searchIndexName": "cwyd-index",
        "semanticConfigurationName": "default",
        "sourceDataFields": [
            {"name": "title"},
            {"name": "url"},
            {"name": "content"},
        ],
    }

    # Knowledge base: references the knowledge source by name and lists the
    # Azure OpenAI chat model used for query planning (Foundry IQ rejects
    # o-series reasoning models here, so this is the chat deployment).
    assert knowledge_base["name"] == "cwyd-kb"
    assert knowledge_base["knowledgeSources"] == [{"name": "cwyd-index-ks"}]
    models = knowledge_base["models"]
    assert isinstance(models, list)
    assert len(models) == 1
    model = models[0]
    assert model["kind"] == "azureOpenAI"
    assert model["azureOpenAIParameters"] == {
        "resourceUri": "https://ai.example/",
        "deploymentId": "chat",
        "modelName": "gpt-5.1",
    }


class _FakeResponse:
    def __init__(self, status_code: int = 200):
        self.status_code = status_code

    def raise_for_status(self) -> None:
        return None


class _FakeHttpClient:
    """Records PUT calls; stands in for httpx.Client (the test seam)."""

    def __init__(self):
        self.puts: list[dict[str, object]] = []
        self.closed = False

    def put(self, url, *, params=None, json=None):
        self.puts.append({"url": url, "params": params, "json": json})
        return _FakeResponse(200)

    def close(self):
        self.closed = True


def _set_kb_env(monkeypatch):
    monkeypatch.setenv("AZURE_AI_SEARCH_ENDPOINT", "https://srch.example/")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://aoai.example/")
    # The KB query-planning model must be a chat model (Foundry IQ
    # rejects o-series reasoning models for the KB; regression guard for
    # the o-series-rejected-by-Foundry-IQ bug).
    monkeypatch.setenv("AZURE_OPENAI_GPT_DEPLOYMENT", "gpt-5.1")


def test_ensure_knowledge_base_skips_when_endpoint_missing(capsys):
    # AZURE_AI_SEARCH_ENDPOINT not set -- postgresql-mode deploy.
    sentinel = {"called": False}

    def factory():
        sentinel["called"] = True
        raise AssertionError("client_factory should not be invoked")

    result = post_provision._ensure_knowledge_base(
        dry_run=False, client_factory=factory
    )

    assert result == "skipped"
    assert sentinel["called"] is False
    assert "skipping knowledge base" in capsys.readouterr().out


def test_ensure_knowledge_base_dry_run_makes_no_calls(monkeypatch, capsys):
    _set_kb_env(monkeypatch)

    def factory():
        raise AssertionError("dry-run must not build a client")

    result = post_provision._ensure_knowledge_base(dry_run=True, client_factory=factory)

    out = capsys.readouterr().out
    assert result == "dry-run"
    assert "[dry-run]" in out
    assert "cwyd-kb" in out


def test_ensure_knowledge_base_requires_openai_config(monkeypatch):
    # Search endpoint set, but no OpenAI endpoint / chat (GPT) deployment.
    monkeypatch.setenv("AZURE_AI_SEARCH_ENDPOINT", "https://srch.example/")
    with pytest.raises(SystemExit) as excinfo:
        post_provision._ensure_knowledge_base(
            dry_run=False, client_factory=lambda: _FakeHttpClient()
        )
    assert excinfo.value.code == 9


def test_ensure_knowledge_base_puts_source_then_base(monkeypatch):
    _set_kb_env(monkeypatch)
    fake = _FakeHttpClient()

    result = post_provision._ensure_knowledge_base(
        dry_run=False, client_factory=lambda: fake
    )

    assert result == "ensured"
    assert fake.closed is True
    # Two PUTs, source before base (the base references the source by name).
    assert len(fake.puts) == 2
    ks_put, kb_put = fake.puts
    assert ks_put["url"] == "https://srch.example/knowledgesources('cwyd-index-ks')"
    assert kb_put["url"] == "https://srch.example/knowledgebases('cwyd-kb')"
    # api-version pinned from the settings default on both calls.
    assert ks_put["params"] == {"api-version": "2025-11-01-preview"}
    assert kb_put["params"] == {"api-version": "2025-11-01-preview"}
    # Bodies are wired from _build_knowledge_base_seed.
    assert ks_put["json"]["kind"] == "searchIndex"
    assert ks_put["json"]["searchIndexParameters"]["searchIndexName"] == "cwyd-index"
    assert kb_put["json"]["knowledgeSources"] == [{"name": "cwyd-index-ks"}]
    aoai = kb_put["json"]["models"][0]["azureOpenAIParameters"]
    assert aoai["resourceUri"] == "https://aoai.example/"
    # KB query planning uses the chat deployment (gpt-5.1), never the
    # o-series reasoning deployment (o4-mini) that Foundry IQ rejects.
    assert aoai["deploymentId"] == "gpt-5.1"
    # Deployment doubles as the model name when no explicit override is set.
    assert aoai["modelName"] == "gpt-5.1"


def test_ensure_knowledge_base_is_idempotent(monkeypatch):
    _set_kb_env(monkeypatch)
    # PUT is create-or-update: a second run "updates" what the first
    # "created", issuing the same two PUTs with no error.
    first = _FakeHttpClient()
    second = _FakeHttpClient()
    clients = iter((first, second))

    assert (
        post_provision._ensure_knowledge_base(
            dry_run=False, client_factory=lambda: next(clients)
        )
        == "ensured"
    )
    assert (
        post_provision._ensure_knowledge_base(
            dry_run=False, client_factory=lambda: next(clients)
        )
        == "ensured"
    )
    assert len(first.puts) == 2
    assert len(second.puts) == 2
    assert [p["url"] for p in first.puts] == [p["url"] for p in second.puts]


def test_main_dry_run_cosmosdb_skips_postgres_and_search_calls(monkeypatch, capsys):
    monkeypatch.setenv("AZURE_DB_TYPE", "cosmosdb")

    rc = post_provision.main(["--dry-run"])

    out = capsys.readouterr().out
    assert rc == 0
    assert "skipping postgres setup" in out
    # Search endpoint not set → skipped path.
    assert "skipping search index" in out


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
# Agent registry bootstrap (no-op closure)
# ---------------------------------------------------------------------------
#
# post_provision.py deliberately makes NO change here. The agent
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
