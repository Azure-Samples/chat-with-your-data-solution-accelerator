"""Guard: the Agent Framework dependency must be the *core* distribution.

The `agent-framework` umbrella meta-package depends on
`agent-framework-hyperlight` (env marker `python_version < "3.14"`),
which requires `hyperlight-sandbox-backend-wasm` -- a dependency pip
cannot resolve on the Functions host's Python 3.11 runtime. With the
umbrella pinned, a remote pip build backtracks forever and the deploy
never completes. The codebase only imports `agent_framework` (core) and
`agent_framework_foundry`, so the dependency must pin
`agent-framework-core`, never the bare `agent-framework` umbrella. This
guard fails if the umbrella creeps back into `[project].dependencies`.
"""

import re
import tomllib
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PYPROJECT = _REPO_ROOT / "pyproject.toml"


def _dependency_names() -> set[str]:
    """Normalized distribution names from `[project].dependencies`."""
    data = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    deps = data["project"]["dependencies"]
    names: set[str] = set()
    for dep in deps:
        # Strip extras, version specifiers, and environment markers to
        # leave the bare distribution name (e.g. "agent-framework-core").
        name = re.split(r"[<>=!~;\[\s]", str(dep), maxsplit=1)[0]
        names.add(name.strip().lower())
    return names


def test_pins_agent_framework_core() -> None:
    """The core distribution must be present."""
    assert "agent-framework-core" in _dependency_names()


def test_does_not_pin_agent_framework_umbrella() -> None:
    """The umbrella meta-package (which pulls hyperlight) must be absent.

    Pulls in `agent-framework-hyperlight` on Python < 3.14, breaking the
    Python 3.11 Functions deploy with an unresolvable
    `hyperlight-sandbox-backend-wasm` requirement.
    """
    assert "agent-framework" not in _dependency_names()
