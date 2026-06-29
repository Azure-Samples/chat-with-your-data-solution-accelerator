"""Tests for the sample-data seed (upload-sample-data.{sh,ps1} + upload_sample_data.py).

Pillar: Stable Core
Phase: 7

The wrappers are thin OS shims azd's project-level `hooks.postdeploy`
invokes after a successful deploy to seed curated documents and enqueue
ingestion so chat grounds out-of-the-box. The wrappers carry no
branching logic, so their contract is textual; the seed behaviour lives
in upload_sample_data.py and is exercised directly with fakes.
"""

import importlib
import json
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
_SH = _SCRIPTS_DIR / "upload-sample-data.sh"
_PS1 = _SCRIPTS_DIR / "upload-sample-data.ps1"


def _load_module():
    """Import upload_sample_data from v2/scripts/ without a top-level import.

    `import upload_sample_data` after a sys.path mutation would trip the
    imports-at-top gate; importlib.import_module is a call, not an import
    statement, so the dynamic load stays compliant.
    """
    sys.path.insert(0, str(_SCRIPTS_DIR))
    sys.modules.pop("upload_sample_data", None)
    try:
        return importlib.import_module("upload_sample_data")
    finally:
        sys.path.remove(str(_SCRIPTS_DIR))


class _FakeBlobClient:
    def __init__(self, name: str, existing: set[str], upload_log: list[tuple[str, bool]]) -> None:
        self._name = name
        self._existing = existing
        self._upload_log = upload_log

    def exists(self) -> bool:
        return self._name in self._existing

    def upload_blob(self, data: bytes, overwrite: bool) -> None:
        self._upload_log.append((self._name, overwrite))
        self._existing.add(self._name)


class _FakeContainerClient:
    def __init__(self, existing: set[str], upload_log: list[tuple[str, bool]]) -> None:
        self._existing = existing
        self._upload_log = upload_log

    def get_blob_client(self, name: str) -> _FakeBlobClient:
        return _FakeBlobClient(name, self._existing, self._upload_log)


class _FakeBlobService:
    def __init__(self, container: _FakeContainerClient) -> None:
        self._container = container
        self.closed = False

    def get_container_client(self, name: str) -> _FakeContainerClient:
        return self._container

    def close(self) -> None:
        self.closed = True


class _FakeQueueClient:
    def __init__(self, sent: list[str]) -> None:
        self._sent = sent
        self.closed = False

    def send_message(self, body: str) -> None:
        self._sent.append(body)

    def close(self) -> None:
        self.closed = True


class _FakeCredential:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def _seed_data_dir(root: Path, names: tuple[str, ...]) -> Path:
    data_dir = root / "data"
    data_dir.mkdir()
    for name in names:
        (data_dir / name).write_bytes(b"%PDF-1.4 sample\n")
    return data_dir


def _install_fakes(
    monkeypatch: pytest.MonkeyPatch,
    module: object,
    existing: set[str],
    upload_log: list[tuple[str, bool]],
    sent: list[str],
) -> tuple[_FakeBlobService, _FakeQueueClient, _FakeCredential]:
    blob_service = _FakeBlobService(_FakeContainerClient(existing, upload_log))
    queue_client = _FakeQueueClient(sent)
    credential = _FakeCredential()
    monkeypatch.setattr(module, "DefaultAzureCredential", lambda *a, **k: credential)
    monkeypatch.setattr(module, "BlobServiceClient", lambda *a, **k: blob_service)
    monkeypatch.setattr(module, "QueueClient", lambda *a, **k: queue_client)
    return blob_service, queue_client, credential


# --- wrapper contract (textual) ----------------------------------------------


def test_both_wrappers_exist() -> None:
    assert _SH.is_file()
    assert _PS1.is_file()


def test_posix_wrapper_fails_fast_and_runs_uploader() -> None:
    body = _SH.read_text(encoding="utf-8")
    assert "Pillar: Stable Core" in body
    assert "set -euo pipefail" in body
    assert "uv run python" in body
    assert "upload_sample_data.py" in body


def test_windows_wrapper_fails_fast_and_runs_uploader() -> None:
    body = _PS1.read_text(encoding="utf-8")
    assert "Pillar: Stable Core" in body
    assert "$ErrorActionPreference = 'Stop'" in body
    assert "uv run python" in body
    assert "upload_sample_data.py" in body


# --- pure helpers ------------------------------------------------------------


def test_resolve_named_files_skips_missing(tmp_path: Path) -> None:
    module = _load_module()
    data_dir = _seed_data_dir(tmp_path, ("Benefit_Options.pdf",))
    files = module.resolve_named_files(data_dir, ("Benefit_Options.pdf", "missing.pdf"))
    assert [p.name for p in files] == ["Benefit_Options.pdf"]


def test_parse_selection_token_maps_known_and_unknown() -> None:
    module = _load_module()
    assert module.parse_selection_token("default") == module.AssistantType.DEFAULT
    assert module.parse_selection_token("Contract") == module.AssistantType.CONTRACT
    assert module.parse_selection_token("employee assistant") == module.AssistantType.EMPLOYEE
    assert module.parse_selection_token("all") == module.SeedScope.ALL
    assert module.parse_selection_token("skip") == module.SeedScope.SKIP
    assert module.parse_selection_token("bogus") is None


def test_files_for_selection_named_contract_and_all(tmp_path: Path) -> None:
    module = _load_module()
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    for name in ("Benefit_Options.pdf", "employee_handbook.pdf", "Woodgrove.pdf"):
        (data_dir / name).write_bytes(b"%PDF-1.4\n")
    contract_dir = data_dir / "contract_data"
    contract_dir.mkdir()
    for name in ("Master_Agreement_V1.pdf", "Legal.PDF"):
        (contract_dir / name).write_bytes(b"%PDF-1.4\n")

    default_names = {p.name for p in module.files_for_selection(data_dir, module.AssistantType.DEFAULT)}
    assert "Benefit_Options.pdf" in default_names
    assert "Woodgrove.pdf" not in default_names

    contract_names = {p.name for p in module.files_for_selection(data_dir, module.AssistantType.CONTRACT)}
    assert contract_names == {"Master_Agreement_V1.pdf", "Legal.PDF"}

    all_names = {p.name for p in module.files_for_selection(data_dir, module.SeedScope.ALL)}
    assert {"Benefit_Options.pdf", "Woodgrove.pdf", "Master_Agreement_V1.pdf", "Legal.PDF"} <= all_names


def test_resolve_selection_cli_and_env_skip_prompt() -> None:
    module = _load_module()
    prompted: list[str] = []

    def _prompt(_: str) -> str:
        prompted.append("called")
        return "1"

    assert module.resolve_selection("contract", "all", True, _prompt, lambda _m: None) == module.AssistantType.CONTRACT
    assert module.resolve_selection("", "all", False, _prompt, lambda _m: None) == module.SeedScope.ALL
    assert prompted == []


def test_resolve_selection_non_tty_defaults() -> None:
    module = _load_module()
    msgs: list[str] = []
    assert module.resolve_selection("", "", False, lambda _p: "1", msgs.append) == module.AssistantType.DEFAULT
    assert any("non-interactive" in m for m in msgs)


def test_resolve_selection_non_tty_none_token_opts_out() -> None:
    module = _load_module()
    assert module.resolve_selection("", "none", False, lambda _p: "1", lambda _m: None) == module.SeedScope.SKIP


def test_resolve_selection_prompts_until_valid_when_tty() -> None:
    module = _load_module()
    answers = iter(["9", "2"])
    selection = module.resolve_selection("", "", True, lambda _p: next(answers), lambda _m: None)
    assert selection == module.AssistantType.CONTRACT


def test_resolve_selection_unknown_token_skips() -> None:
    module = _load_module()
    msgs: list[str] = []
    assert module.resolve_selection("bogus", "", True, lambda _p: "1", msgs.append) == module.SeedScope.SKIP
    assert any("unknown sample-data selection" in m for m in msgs)


def test_resolve_endpoints_default_and_override() -> None:
    module = _load_module()
    blob, queue = module.resolve_endpoints("acct", "")
    assert blob == "https://acct.blob.core.windows.net"
    assert queue == "https://acct.queue.core.windows.net"
    blob_gov, queue_gov = module.resolve_endpoints("acct", "https://acct.blob.core.usgovcloudapi.net")
    assert blob_gov == "https://acct.blob.core.usgovcloudapi.net"
    assert queue_gov == "https://acct.queue.core.usgovcloudapi.net"


def test_upload_blob_if_absent_skips_existing() -> None:
    module = _load_module()
    upload_log: list[tuple[str, bool]] = []
    container = _FakeContainerClient({"Benefit_Options.pdf"}, upload_log)
    uploaded = module.upload_blob_if_absent(container, Path("Benefit_Options.pdf"))
    assert uploaded is False
    assert upload_log == []


def test_upload_blob_if_absent_uploads_new(tmp_path: Path) -> None:
    module = _load_module()
    upload_log: list[tuple[str, bool]] = []
    container = _FakeContainerClient(set(), upload_log)
    file_path = tmp_path / "PerksPlus.pdf"
    file_path.write_bytes(b"%PDF-1.4 sample\n")
    uploaded = module.upload_blob_if_absent(container, file_path)
    assert uploaded is True
    assert upload_log == [("PerksPlus.pdf", False)]


def test_enqueue_ingest_message_sends_raw_json() -> None:
    module = _load_module()
    sent: list[str] = []
    module.enqueue_ingest_message(_FakeQueueClient(sent), "documents", "Benefit_Options.pdf")
    assert len(sent) == 1
    payload = json.loads(sent[0])
    assert payload["container_name"] == "documents"
    assert payload["filename"] == "Benefit_Options.pdf"


def test_wait_for_index_completion_passes_when_count_reaches_min() -> None:
    module = _load_module()
    counts = iter([0, 2, 5])
    outputs: list[str] = []
    slept: list[float] = []
    result = module.wait_for_index_completion(
        lambda: next(counts),
        5,
        100.0,
        1.0,
        slept.append,
        lambda: 0.0,
        outputs.append,
    )
    assert result is True
    assert any("PASS" in m for m in outputs)
    assert slept == [1.0, 1.0]


def test_wait_for_index_completion_fails_on_timeout_with_remediation() -> None:
    module = _load_module()
    outputs: list[str] = []
    slept: list[float] = []
    clock = iter([0.0, 5.0, 10.0, 20.0])
    result = module.wait_for_index_completion(
        lambda: 0,
        3,
        15.0,
        2.0,
        slept.append,
        lambda: next(clock),
        outputs.append,
    )
    assert result is False
    assert any("FAIL" in m for m in outputs)
    assert any("doc-processing-poison" in m for m in outputs)
    assert any("/api/health" in m for m in outputs)
    assert slept == [2.0, 2.0]


# --- main() ------------------------------------------------------------------


def test_missing_required_env_exits_2(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_module()
    for name in ("AZURE_STORAGE_ACCOUNT_NAME", "AZURE_DOCUMENTS_CONTAINER", "AZURE_DOC_PROCESSING_QUEUE"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(SystemExit) as exc:
        module.main([])
    assert exc.value.code == 2


def test_dry_run_makes_no_sdk_calls(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_module()
    data_dir = _seed_data_dir(tmp_path, module.SAMPLE_SETS[module.AssistantType.DEFAULT])
    monkeypatch.setattr(module, "_curated_data_dir", lambda: data_dir)
    monkeypatch.setenv("AZURE_STORAGE_ACCOUNT_NAME", "sampleacct")
    monkeypatch.setenv("AZURE_DOCUMENTS_CONTAINER", "documents")
    monkeypatch.setenv("AZURE_DOC_PROCESSING_QUEUE", "doc-processing")

    def _boom(*args: object, **kwargs: object) -> object:
        raise AssertionError("dry-run must not construct Azure SDK clients")

    monkeypatch.setattr(module, "DefaultAzureCredential", _boom)
    monkeypatch.setattr(module, "BlobServiceClient", _boom)
    monkeypatch.setattr(module, "QueueClient", _boom)
    assert module.main(["--dry-run", "--set", "default"]) == 0


def test_main_skips_when_scope_none(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_module()
    monkeypatch.setenv("AZURE_STORAGE_ACCOUNT_NAME", "sampleacct")
    monkeypatch.setenv("AZURE_DOCUMENTS_CONTAINER", "documents")
    monkeypatch.setenv("AZURE_DOC_PROCESSING_QUEUE", "doc-processing")

    def _boom(*args: object, **kwargs: object) -> object:
        raise AssertionError("the skip path must not touch Azure")

    monkeypatch.setattr(module, "DefaultAzureCredential", _boom)
    assert module.main(["--set", "none"]) == 0


def test_main_uploads_and_enqueues_then_is_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_module()
    sample = module.SAMPLE_SETS[module.AssistantType.DEFAULT]
    data_dir = _seed_data_dir(tmp_path, sample)
    monkeypatch.setattr(module, "_curated_data_dir", lambda: data_dir)
    monkeypatch.setenv("AZURE_STORAGE_ACCOUNT_NAME", "sampleacct")
    monkeypatch.setenv("AZURE_DOCUMENTS_CONTAINER", "documents")
    monkeypatch.setenv("AZURE_DOC_PROCESSING_QUEUE", "doc-processing")
    monkeypatch.delenv("AZURE_INGESTION_TRIGGER", raising=False)

    existing: set[str] = set()
    upload_log: list[tuple[str, bool]] = []
    sent: list[str] = []
    blob_service, queue_client, credential = _install_fakes(monkeypatch, module, existing, upload_log, sent)

    assert module.main(["--set", "default"]) == 0
    expected = sorted(sample)
    assert sorted(name for name, _ in upload_log) == expected
    assert all(overwrite is False for _, overwrite in upload_log)
    assert sorted(json.loads(body)["filename"] for body in sent) == expected
    assert blob_service.closed and queue_client.closed and credential.closed

    # Second run with the same backing store is a no-op: nothing re-uploaded
    # and nothing re-enqueued.
    assert module.main(["--set", "default"]) == 0
    assert sorted(name for name, _ in upload_log) == expected
    assert sorted(json.loads(body)["filename"] for body in sent) == expected


def test_main_event_grid_suppresses_enqueue(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_module()
    sample = module.SAMPLE_SETS[module.AssistantType.DEFAULT]
    data_dir = _seed_data_dir(tmp_path, sample)
    monkeypatch.setattr(module, "_curated_data_dir", lambda: data_dir)
    monkeypatch.setenv("AZURE_STORAGE_ACCOUNT_NAME", "sampleacct")
    monkeypatch.setenv("AZURE_DOCUMENTS_CONTAINER", "documents")
    monkeypatch.setenv("AZURE_DOC_PROCESSING_QUEUE", "doc-processing")
    monkeypatch.setenv("AZURE_INGESTION_TRIGGER", "event_grid")

    existing: set[str] = set()
    upload_log: list[tuple[str, bool]] = []
    sent: list[str] = []
    _install_fakes(monkeypatch, module, existing, upload_log, sent)

    assert module.main(["--set", "default"]) == 0
    assert sorted(name for name, _ in upload_log) == sorted(sample)
    assert sent == []
