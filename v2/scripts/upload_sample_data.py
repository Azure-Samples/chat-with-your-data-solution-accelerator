"""Post-deploy seed: upload sample documents and enqueue ingestion.

Pillar: Stable Core
Phase:  7 (post-deploy sample-data seed)

Runs after a successful ``azd deploy`` / ``azd up`` so chat grounds
out-of-the-box without an operator manually uploading documents. The
operator chooses which assistant scenario to seed -- ``default`` /
``employee assistant`` (benefits / HR documents) or ``contract
assistant`` (contract documents) -- or ``all`` to seed every sample
document. The scope is taken from ``--set``, then the
``AZURE_ENV_SAMPLE_DATA`` env override, then an interactive menu when the
hook runs in a terminal; a non-interactive shell with no override seeds
the default PDF document set so chat grounds out-of-the-box (set
``AZURE_ENV_SAMPLE_DATA=none`` to opt out). Files resolve from the
repo-root ``data/`` folder; no binary documents are committed.

Behaviour mirrors the admin upload path (``backend.services.ingestion``):
each newly-uploaded blob is followed by an ingestion message on the
doc-processing queue using the shared ``BatchPushQueueMessage`` contract.
The queue client is built without a base64 encode policy so it sends raw
JSON, matching the function host's ``messageEncoding: none``. The seed is
idempotent: blobs already present in the target container are skipped
(no re-upload, no re-enqueue). Enqueueing only happens in direct-enqueue
mode; under event-grid ingestion the blob upload alone triggers
processing, so enqueueing is suppressed to avoid double-ingestion.

Authentication uses ``DefaultAzureCredential`` (matches
``post_provision.py``). Pass ``--dry-run`` to print the planned actions
without touching Azure.
"""

import argparse
import os
import sys
import time
from collections.abc import Callable, Sequence
from enum import StrEnum
from pathlib import Path

from azure.core.exceptions import AzureError, HttpResponseError
from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from azure.storage.blob import BlobServiceClient, ContainerClient
from azure.storage.queue import QueueClient

from backend.core.agents.presets import AssistantType
from backend.core.settings import IngestionTrigger
from functions.core.contracts import BatchPushQueueMessage


class SeedScope(StrEnum):
    """Non-persona seed scopes that sit alongside the AssistantType set."""

    ALL = "all"
    SKIP = "none"


# A seed selection is an AssistantType persona or a SeedScope (all / skip).
Selection = AssistantType | SeedScope

# Curated benefits / HR document set, shared by the default + employee
# personas. Names resolve from the repo-root data/ folder; a missing
# named file is skipped with a warning rather than failing the seed.
_BENEFITS_SET = (
    "Benefit_Options.pdf",
    "employee_handbook.pdf",
    "PerksPlus.pdf",
    "role_library.pdf",
    "Northwind_Standard_Benefits_Details.pdf",
    "Northwind_Health_Plus_Benefits_Details.pdf",
)
SAMPLE_SETS: dict[Selection, tuple[str, ...]] = {
    AssistantType.DEFAULT: _BENEFITS_SET,
    AssistantType.EMPLOYEE: _BENEFITS_SET,
}

#: Subdirectory under data/ holding the contract-assistant corpus (globbed).
_CONTRACT_DIR = "contract_data"

#: Document extensions seeded by the contract / all scopes.
_DOC_PATTERNS = ("*.pdf", "*.PDF", "*.docx", "*.DOCX")

#: Accepted ``--set`` / ``AZURE_ENV_SAMPLE_DATA`` tokens (case-insensitive).
_SELECTION_TOKENS: dict[str, Selection] = {
    "default": AssistantType.DEFAULT,
    "contract": AssistantType.CONTRACT,
    "contract assistant": AssistantType.CONTRACT,
    "employee": AssistantType.EMPLOYEE,
    "employee assistant": AssistantType.EMPLOYEE,
    "all": SeedScope.ALL,
    "none": SeedScope.SKIP,
    "skip": SeedScope.SKIP,
}

#: Interactive menu rows: (key, selection, label).
_MENU: tuple[tuple[str, Selection, str], ...] = (
    ("1", AssistantType.DEFAULT, "Default (general / benefits documents)"),
    ("2", AssistantType.CONTRACT, "Contract assistant (contract documents)"),
    ("3", AssistantType.EMPLOYEE, "Employee assistant (HR / benefits documents)"),
    ("4", SeedScope.ALL, "All sample documents"),
    ("0", SeedScope.SKIP, "Skip (do not seed)"),
)
_MENU_DEFAULT_KEY = "4"

# Required azd output environment variables.
_ENV_ACCOUNT = "AZURE_STORAGE_ACCOUNT_NAME"
_ENV_CONTAINER = "AZURE_DOCUMENTS_CONTAINER"
_ENV_QUEUE = "AZURE_DOC_PROCESSING_QUEUE"

# Optional overrides. Blob endpoint override keeps the seed sovereign-cloud
# safe; ingestion trigger selects whether the producer enqueues; the sample
# data override picks the scope unattended.
_ENV_BLOB_ENDPOINT = "AZURE_STORAGE_BLOB_ENDPOINT"
_ENV_INGESTION_TRIGGER = "AZURE_INGESTION_TRIGGER"
_ENV_SAMPLE_DATA = "AZURE_ENV_SAMPLE_DATA"

# Azure AI Search outputs. When both are present the seed runs a bounded
# post-enqueue poll that confirms the freshly seeded documents became
# searchable; when either is absent the completion check is skipped.
_ENV_SEARCH_ENDPOINT = "AZURE_AI_SEARCH_ENDPOINT"
_ENV_SEARCH_INDEX = "AZURE_AI_SEARCH_INDEX"

# Bounded index-completion poll. Ingestion runs asynchronously (the seed
# enqueues and returns; batch_push indexes), so poll until the new documents
# are searchable or the timeout owns the verdict.
_INDEX_WAIT_TIMEOUT_S = 300.0
_INDEX_WAIT_INTERVAL_S = 10.0

# Loud rule that frames the post-seed PASS / FAIL verdict banner.
_BANNER_RULE = "=" * 64

_EXIT_MISSING_ENV = 2
_EXIT_SDK_FAILURE = 6


def _require(name: str) -> str:
    """Return a required non-empty environment variable or exit non-zero."""
    value = os.environ.get(name, "").strip()
    if not value:
        sys.stderr.write(f"upload-sample-data: required environment variable {name} is not set.\n")
        sys.exit(_EXIT_MISSING_ENV)
    return value


def _curated_data_dir() -> Path:
    """Return the repo-root data/ folder that holds the sample corpus."""
    return Path(__file__).resolve().parents[2] / "data"


def parse_selection_token(token: str) -> Selection | None:
    """Map a ``--set`` / env token to a Selection, or None when unknown."""
    return _SELECTION_TOKENS.get(token.strip().lower())


def _glob_docs(directory: Path) -> list[Path]:
    """Return PDF/DOCX files directly under ``directory`` (non-recursive)."""
    found: set[Path] = set()
    for pattern in _DOC_PATTERNS:
        found.update(path for path in directory.glob(pattern) if path.is_file())
    return sorted(found)


def resolve_named_files(data_dir: Path, filenames: Sequence[str]) -> list[Path]:
    """Return existing named files under ``data_dir``; skip + warn on missing."""
    resolved: list[Path] = []
    for name in filenames:
        candidate = data_dir / name
        if candidate.is_file():
            resolved.append(candidate)
        else:
            sys.stderr.write(f"upload-sample-data: sample file {name} not found in {data_dir}; skipping.\n")
    return resolved


def files_for_selection(data_dir: Path, selection: Selection) -> list[Path]:
    """Return the sample files to seed for ``selection`` (uploaded by basename)."""
    if selection == SeedScope.ALL:
        return _glob_docs(data_dir) + _glob_docs(data_dir / _CONTRACT_DIR)
    if selection == AssistantType.CONTRACT:
        return _glob_docs(data_dir / _CONTRACT_DIR)
    return resolve_named_files(data_dir, SAMPLE_SETS.get(selection, ()))


def _menu_text() -> str:
    """Return the interactive scenario menu text."""
    rows = [f"  {key}) {label}" for key, _selection, label in _MENU]
    return "\n".join(["", "Sample data -- choose an assistant scenario to seed:", *rows])


def prompt_menu(prompt_fn: Callable[[str], str], output_fn: Callable[[str], None]) -> Selection:
    """Show the menu and read a choice until one is valid."""
    by_key: dict[str, Selection] = {key: selection for key, selection, _label in _MENU}
    output_fn(_menu_text())
    while True:
        choice = prompt_fn(f"Enter choice [{_MENU_DEFAULT_KEY}]: ").strip() or _MENU_DEFAULT_KEY
        selection = by_key.get(choice)
        if selection is not None:
            return selection
        output_fn("upload-sample-data: invalid choice; enter 0-4.")


def resolve_selection(
    cli_value: str,
    env_value: str,
    is_tty: bool,
    prompt_fn: Callable[[str], str],
    output_fn: Callable[[str], None],
) -> Selection:
    """Resolve the seed scope: ``--set`` > env override > menu (TTY) > skip."""
    token = cli_value or env_value
    if token:
        selection = parse_selection_token(token)
        if selection is None:
            output_fn(
                f"upload-sample-data: unknown sample-data selection '{token}'; "
                "expected default|contract|employee|all|none. Skipping."
            )
            return SeedScope.SKIP
        return selection
    if not is_tty:
        output_fn(
            "upload-sample-data: non-interactive shell and no AZURE_ENV_SAMPLE_DATA "
            "override; seeding the default PDF document set so chat grounds "
            "out-of-the-box. Set AZURE_ENV_SAMPLE_DATA=none to opt out, or "
            "default|contract|employee|all to choose a different scope."
        )
        return AssistantType.DEFAULT
    return prompt_menu(prompt_fn, output_fn)


def resolve_endpoints(account_name: str, blob_endpoint_override: str) -> tuple[str, str]:
    """Return ``(blob_endpoint, queue_endpoint)`` for the storage account."""
    blob_endpoint = blob_endpoint_override or f"https://{account_name}.blob.core.windows.net"
    queue_endpoint = blob_endpoint.replace(".blob.", ".queue.", 1)
    return blob_endpoint, queue_endpoint


def upload_blob_if_absent(container_client: ContainerClient, file_path: Path) -> bool:
    """Upload ``file_path`` as a blob unless it already exists.

    Returns ``True`` when the blob was uploaded, ``False`` when it was
    already present and therefore skipped.
    """
    blob_client = container_client.get_blob_client(file_path.name)
    if blob_client.exists():
        return False
    blob_client.upload_blob(file_path.read_bytes(), overwrite=False)
    return True


def enqueue_ingest_message(queue_client: QueueClient, container_name: str, filename: str) -> None:
    """Send a raw-JSON ingestion message for one uploaded blob."""
    message = BatchPushQueueMessage(container_name=container_name, filename=filename)
    queue_client.send_message(message.model_dump_json())


def wait_for_index_completion(
    count_fn: Callable[[], int],
    expected_min: int,
    timeout_s: float,
    interval_s: float,
    sleep_fn: Callable[[float], None],
    monotonic_fn: Callable[[], float],
    output_fn: Callable[[str], None],
) -> bool:
    """Poll the index until it holds ``expected_min`` documents or time runs out.

    Returns ``True`` once ``count_fn()`` reports at least ``expected_min``
    documents and prints a loud PASS banner. Returns ``False`` when
    ``timeout_s`` elapses with the index still short, printing a loud FAIL
    banner plus a remediation hint. All waiting and timing flow through the
    injected ``sleep_fn`` / ``monotonic_fn`` so callers own the clock.
    """
    start = monotonic_fn()
    while True:
        count = count_fn()
        if count >= expected_min:
            output_fn(_BANNER_RULE)
            output_fn(
                f"upload-sample-data: PASS -- index reached {count} document(s) "
                f"(expected at least {expected_min}); seeded documents are searchable."
            )
            output_fn(_BANNER_RULE)
            return True
        if monotonic_fn() - start >= timeout_s:
            output_fn(_BANNER_RULE)
            output_fn(
                f"upload-sample-data: FAIL -- index holds {count} document(s) after "
                f"{timeout_s:.0f}s; expected at least {expected_min}. The seed uploaded "
                "and enqueued documents, but they are not searchable yet."
            )
            output_fn(
                "  Remediation: inspect the 'doc-processing-poison' queue for failed "
                "ingestion messages and check the function host '/api/health' endpoint."
            )
            output_fn(_BANNER_RULE)
            return False
        sleep_fn(interval_s)


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed sample documents and enqueue ingestion.")
    parser.add_argument(
        "--set",
        dest="scope",
        default="",
        help="Seed scope without prompting: default|contract|employee|all|none.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the planned uploads without authenticating or touching Azure.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)

    account_name = _require(_ENV_ACCOUNT)
    container_name = _require(_ENV_CONTAINER)
    queue_name = _require(_ENV_QUEUE)
    blob_endpoint_override = os.environ.get(_ENV_BLOB_ENDPOINT, "").strip()
    trigger = os.environ.get(_ENV_INGESTION_TRIGGER, "").strip() or IngestionTrigger.DIRECT_ENQUEUE
    enqueue = trigger == IngestionTrigger.DIRECT_ENQUEUE
    search_endpoint = os.environ.get(_ENV_SEARCH_ENDPOINT, "").strip()
    search_index = os.environ.get(_ENV_SEARCH_INDEX, "").strip()

    selection = resolve_selection(
        args.scope,
        os.environ.get(_ENV_SAMPLE_DATA, "").strip(),
        sys.stdin.isatty(),
        input,
        print,
    )
    if selection == SeedScope.SKIP:
        print("upload-sample-data: no scenario selected; skipping seed.")
        return 0

    data_dir = _curated_data_dir()
    files = files_for_selection(data_dir, selection)
    if not files:
        sys.stderr.write(f"upload-sample-data: no sample files found for '{selection}' in {data_dir}; nothing to seed.\n")
        return 0

    if args.dry_run:
        print(f"upload-sample-data: scope '{selection}' -> {len(files)} document(s).")
        for file_path in files:
            action = f"upload {file_path.name} -> {container_name}"
            if enqueue:
                action += f" + enqueue -> {queue_name}"
            print(f"[dry-run] {action}")
        return 0

    blob_endpoint, queue_endpoint = resolve_endpoints(account_name, blob_endpoint_override)
    credential = DefaultAzureCredential()
    blob_service = BlobServiceClient(account_url=blob_endpoint, credential=credential)
    container_client = blob_service.get_container_client(container_name)
    queue_client = QueueClient(
        account_url=queue_endpoint,
        queue_name=queue_name,
        credential=credential,
        message_encode_policy=None,
    )
    search_client = None
    if search_endpoint and search_index:
        search_client = SearchClient(endpoint=search_endpoint, index_name=search_index, credential=credential)

    last_known_count = 0

    def _index_document_count() -> int:
        """Return the live index document count, holding last-known on a transient poll error."""
        nonlocal last_known_count
        try:
            last_known_count = search_client.get_document_count()
        except (AzureError, HttpResponseError) as exc:
            sys.stderr.write(
                "upload-sample-data: index document-count poll failed; holding last-known "
                f"count and retrying. Details: {exc}\n"
            )
        return last_known_count

    uploaded = 0
    skipped = 0
    try:
        baseline = _index_document_count() if search_client is not None else 0
        for file_path in files:
            if upload_blob_if_absent(container_client, file_path):
                uploaded += 1
                if enqueue:
                    enqueue_ingest_message(queue_client, container_name, file_path.name)
                print(f"upload-sample-data: uploaded {file_path.name}.")
            else:
                skipped += 1
                print(f"upload-sample-data: {file_path.name} already present; skipping.")

        if search_client is None:
            print(
                "upload-sample-data: AZURE_AI_SEARCH_ENDPOINT / AZURE_AI_SEARCH_INDEX not set; "
                "skipping the post-seed index-completion check."
            )
        elif uploaded > 0:
            wait_for_index_completion(
                _index_document_count,
                baseline + uploaded,
                _INDEX_WAIT_TIMEOUT_S,
                _INDEX_WAIT_INTERVAL_S,
                time.sleep,
                time.monotonic,
                print,
            )
    except AzureError as exc:
        sys.stderr.write(
            "upload-sample-data: storage operation failed; ensure the deployer identity has "
            "Storage Blob Data Contributor and Storage Queue Data Message Sender on the account "
            f"({account_name}). Details: {exc}\n"
        )
        return _EXIT_SDK_FAILURE
    finally:
        if search_client is not None:
            search_client.close()
        queue_client.close()
        blob_service.close()
        credential.close()

    print(f"upload-sample-data: uploaded {uploaded}, skipped {skipped} (already present).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
