"""Repo invariant: no tracked file contains this machine's real azd env values.

Per ``.github/copilot-instructions.md`` Hard Rule #18 and
``v2/docs/adr/0019-no-env-specific-content-in-tracked-files.md``, no tracked
file may carry real environment values (subscription / tenant ids, resource
group, azd env name, resource-name suffix, individual resource names, deployer
principal ids). Real values live only in the gitignored ``.azure/<env>/.env``
and the operator's ``az`` / ``azd`` session.

ADR-0019 was discipline-only until this gate: the same class of leak recurred
across sessions because nothing enforced it. This gate closes that gap without
ever hard-coding a secret -- it reads the developer's own live azd environment
(the gitignored dotenv), builds a denylist of the env-specific values that
environment actually holds, and asserts that **no git-tracked file** contains
any of them. It runs where a leak originates: the developer's machine, which
has ``.azure/``. On a fresh clone or a CI runner that never provisioned there
is no local env, so the live check ``skip``s -- there is nothing local to leak.
The detection + derivation mechanism is unit-tested below so the logic stays
covered regardless of whether a live env is present.

Only genuinely env-specific keys are denied (subscription, tenant, resource
group, env name, resource-name vars, principal ids). Region, model-name,
boolean, index-name, and generic-endpoint values are excluded so legitimate
technical content (``eastus2``, ``text-embedding-3-small``, ``cwyd-index``)
never trips the gate. Values shorter than ``_MIN_VALUE_LEN`` or listed in
``_GENERIC_VALUES`` are ignored so common tokens cannot match. The resource
suffix -- which is not a standalone env var -- is derived as the longest
common trailing run shared by the resource-name values.
"""

import json
import subprocess
from collections.abc import Iterable
from pathlib import Path

import pytest

# Repo root resolves from this file: tests/shared/test_*.py -> repo root.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_AZURE_DIR = _REPO_ROOT / ".azure"

# azd env-var keys whose VALUES are env-specific per ADR-0019. Region /
# model-name / boolean / generic-endpoint keys are intentionally absent so
# legitimate technical content never lands on the denylist.
_SENSITIVE_KEYS: frozenset[str] = frozenset(
    {
        "AZURE_SUBSCRIPTION_ID",
        "AZURE_TENANT_ID",
        "AZURE_RESOURCE_GROUP",
        "AZURE_ENV_NAME",
        "AZURE_STORAGE_ACCOUNT_NAME",
        "AZURE_FUNCTION_APP_NAME",
        "AZURE_AI_SEARCH_NAME",
        "AZURE_SEARCH_SERVICE",
        "AZURE_COSMOS_ACCOUNT_NAME",
        "AZURE_CONTAINER_REGISTRY_NAME",
        "AZURE_PRINCIPAL_ID",
        "AZURE_PRINCIPAL_NAME",
        "AZURE_CLIENT_ID",
    }
)

# Resource-name-ish keys used to derive the shared deployment suffix.
_RESOURCE_NAME_KEYS: frozenset[str] = frozenset(
    {
        "AZURE_STORAGE_ACCOUNT_NAME",
        "AZURE_FUNCTION_APP_NAME",
        "AZURE_AI_SEARCH_NAME",
        "AZURE_SEARCH_SERVICE",
        "AZURE_COSMOS_ACCOUNT_NAME",
        "AZURE_CONTAINER_REGISTRY_NAME",
    }
)

_MIN_VALUE_LEN = 6

# Non-secret values that may legitimately appear as an env-var value -- regions,
# database kinds, index-store keys, the fixed index name, common enum values.
_GENERIC_VALUES: frozenset[str] = frozenset(
    {
        "eastus",
        "eastus2",
        "westus",
        "westus2",
        "uksouth",
        "cosmosdb",
        "postgresql",
        "azuresearch",
        "cwyd-index",
        "production",
        "local",
        "true",
        "false",
    }
)

# Binary / non-text extensions to skip when scanning tracked files.
_SKIP_SUFFIXES: frozenset[str] = frozenset(
    {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".ico",
        ".pdf",
        ".zip",
        ".gz",
        ".pyc",
        ".woff",
        ".woff2",
        ".ttf",
        ".eot",
        ".lock",
    }
)


def _parse_dotenv(text: str) -> dict[str, str]:
    """Parse simple ``KEY=VALUE`` / ``KEY="VALUE"`` dotenv lines."""
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        out[key.strip()] = value.strip().strip('"').strip("'")
    out.pop("", None)
    return out


def _longest_common_suffix(values: list[str]) -> str:
    """Return the longest common trailing substring across ``values``."""
    if len(values) < 2:
        return ""
    shortest = min(values, key=len)
    suffix = ""
    for i in range(1, len(shortest) + 1):
        candidate = shortest[-i:]
        if all(v.endswith(candidate) for v in values):
            suffix = candidate
        else:
            break
    return suffix


def _build_denylist(values: dict[str, str]) -> dict[str, str]:
    """Map ``denied value -> source label`` from parsed azd env values."""
    denylist: dict[str, str] = {}
    for key in _SENSITIVE_KEYS:
        value = values.get(key, "").strip()
        if len(value) >= _MIN_VALUE_LEN and value.lower() not in _GENERIC_VALUES:
            denylist[value] = key

    resource_names = [
        values[key].strip()
        for key in _RESOURCE_NAME_KEYS
        if len(values.get(key, "").strip()) >= _MIN_VALUE_LEN
    ]
    suffix = _longest_common_suffix(resource_names)
    if len(suffix) >= _MIN_VALUE_LEN and suffix.lower() not in _GENERIC_VALUES:
        denylist.setdefault(suffix, "derived resource suffix")
    return denylist


def _find_leaks(
    files: Iterable[tuple[str, str]], denylist: dict[str, str]
) -> list[str]:
    """Return ``"<relpath>: leaks <source>"`` for each file containing a value."""
    hits: list[str] = []
    for rel, content in files:
        for value, source in denylist.items():
            if value in content:
                hits.append(f"{rel}: leaks the value of {source}")
    return hits


def _load_env_denylist() -> dict[str, str]:
    """Build the denylist from the live azd env, or ``{}`` when none is present."""
    config = _AZURE_DIR / "config.json"
    if not config.is_file():
        return {}
    try:
        env_name = json.loads(config.read_text(encoding="utf-8")).get(
            "defaultEnvironment"
        )
    except (json.JSONDecodeError, OSError):
        return {}
    if not env_name:
        return {}
    dotenv = _AZURE_DIR / str(env_name) / ".env"
    if not dotenv.is_file():
        return {}
    return _build_denylist(_parse_dotenv(dotenv.read_text(encoding="utf-8")))


def _tracked_text_files() -> list[Path]:
    """Return git-tracked files (absolute paths), minus binary extensions."""
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return []
    files: list[Path] = []
    for rel in result.stdout.split("\0"):
        name = rel.strip()
        if not name:
            continue
        path = _REPO_ROOT / name
        if path.suffix.lower() in _SKIP_SUFFIXES:
            continue
        files.append(path)
    return files


def _scan_tracked(denylist: dict[str, str]) -> list[str]:
    """Scan every tracked text file for any denied value."""

    def _pairs() -> Iterable[tuple[str, str]]:
        for path in _tracked_text_files():
            try:
                content = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            yield path.relative_to(_REPO_ROOT).as_posix(), content

    return _find_leaks(_pairs(), denylist)


def test_no_tracked_file_leaks_local_env_values() -> None:
    """No git-tracked file may contain a real value from the live azd env."""
    denylist = _load_env_denylist()
    if not denylist:
        pytest.skip(
            "No azd env under .azure/; the env-ID leak gate is a "
            "developer-machine safety net and has nothing local to compare."
        )
    hits = sorted(set(_scan_tracked(denylist)))
    assert not hits, (
        "Tracked files contain real environment-specific values (Hard Rule "
        "#18 / ADR-0019). Replace with placeholders (<SUFFIX>, <AZD_ENV_NAME>, "
        "<RESOURCE_GROUP>, <AZURE_SUBSCRIPTION_ID>, ...):\n  " + "\n  ".join(hits)
    )


# --- Mechanism unit tests (run regardless of a live azd env) -----------------


def test_parse_dotenv_handles_quotes_comments_blanks() -> None:
    parsed = _parse_dotenv(
        "# comment\n"
        'AZURE_ENV_NAME="my-env"\n'
        "\n"
        "AZURE_RESOURCE_GROUP=rg-my-env\n"
        "EMPTY=\n"
        "= badkey\n"
    )
    assert parsed["AZURE_ENV_NAME"] == "my-env"
    assert parsed["AZURE_RESOURCE_GROUP"] == "rg-my-env"
    assert parsed["EMPTY"] == ""
    assert "" not in parsed


def test_longest_common_suffix_derives_shared_token() -> None:
    assert _longest_common_suffix(["stabc123xyz", "ca-func-abc123xyz"]) == "abc123xyz"
    assert _longest_common_suffix(["only-one"]) == ""
    assert _longest_common_suffix(["foo", "bar"]) == ""
    # A short coincidental suffix can be returned; the _MIN_VALUE_LEN guard in
    # _build_denylist filters it before it can reach the denylist.
    assert _longest_common_suffix(["alpha", "beta"]) == "a"


def test_build_denylist_excludes_generic_and_short_values() -> None:
    denylist = _build_denylist(
        {
            "AZURE_SUBSCRIPTION_ID": "11111111-2222-3333-4444-555555555555",
            "AZURE_ENV_NAME": "contoso-rag-prod",
            "AZURE_RESOURCE_GROUP": "rg-contoso-rag-prod",
            "AZURE_STORAGE_ACCOUNT_NAME": "stcontosorag99",
            "AZURE_FUNCTION_APP_NAME": "ca-func-contosorag99",
            "AZURE_LOCATION": "eastus2",  # not a sensitive key -> ignored
        }
    )
    assert denylist["11111111-2222-3333-4444-555555555555"] == "AZURE_SUBSCRIPTION_ID"
    assert denylist["contoso-rag-prod"] == "AZURE_ENV_NAME"
    assert "eastus2" not in denylist  # region excluded
    # Suffix derived from the two resource names.
    assert "contosorag99" in denylist


def test_find_leaks_detects_planted_value_and_passes_when_clean() -> None:
    denylist = {"contosorag99": "derived resource suffix"}
    leaked = _find_leaks(
        [("docs/notes.md", "deployed to stcontosorag99 last night")], denylist
    )
    assert leaked == ["docs/notes.md: leaks the value of derived resource suffix"]
    clean = _find_leaks(
        [("docs/notes.md", "deployed to st<SUFFIX> last night")], denylist
    )
    assert clean == []
