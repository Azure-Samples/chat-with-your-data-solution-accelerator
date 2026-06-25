"""Pillar: Stable Core
Phase: 1

Assemble the App Service deploy artifact for the `frontend` service at
``v2/src/frontend/build-output/``. azd packages whatever the
``services.frontend.dist`` path points at (set to ``./build-output`` in
``azure.yaml``), and the App Service start command runs
``uvicorn frontend_app:app``. That command needs three things at the
deploy root, none of which the Vite ``dist/`` output alone provides:

1. ``frontend_app.py`` -- the ASGI server that serves the SPA and the
   ``/config`` endpoint -- at the import root.
2. ``requirements.txt`` -- so the App Service Oryx build installs
   fastapi + uvicorn before the start command runs.
3. ``dist/`` -- the built SPA, in a subdirectory beside the server so
   ``frontend_app``'s module-relative ``DIST_DIR`` default resolves.

The build-output directory is gitignored and recreated from scratch on
every invocation -- never edit it by hand. The prepackage wrappers
(``package-frontend.{sh,ps1}``) run ``npm ci && npm run build`` first,
then invoke this script to stage the artifact.
"""

import shutil
import sys
from pathlib import Path

_V2_ROOT = Path(__file__).resolve().parents[1]
_FRONTEND = _V2_ROOT / "src" / "frontend"
_BUILD = _FRONTEND / "build-output"
_SERVER_MODULE = "frontend_app.py"

# Server-only runtime deps for the App Service Oryx build, pinned to the
# backend's fastapi/uvicorn so the static host and the API share one
# version line.
_REQUIREMENTS = (
    "fastapi==0.133.0",
    "uvicorn[standard]>=0.34,<1.0",
)


def build_artifact(frontend_dir: Path, build_dir: Path) -> None:
    """Stage server + requirements + built SPA into ``build_dir``.

    Raises ``FileNotFoundError`` when the Vite ``dist/`` output is
    missing (the wrappers run ``npm run build`` before calling this).
    """
    dist_src = frontend_dir / "dist"
    if not dist_src.is_dir():
        raise FileNotFoundError(
            f"Vite build output not found: {dist_src} (run `npm run build` first)"
        )
    if build_dir.exists():
        shutil.rmtree(build_dir)
    build_dir.mkdir(parents=True)
    shutil.copytree(dist_src, build_dir / "dist")
    shutil.copy2(frontend_dir / _SERVER_MODULE, build_dir / _SERVER_MODULE)
    (build_dir / "requirements.txt").write_text(
        "\n".join(_REQUIREMENTS) + "\n", encoding="utf-8"
    )


def main() -> int:
    build_artifact(_FRONTEND, _BUILD)
    print(f"frontend deploy artifact staged at {_BUILD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
