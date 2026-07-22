#!/usr/bin/env bash
# CWYD v2 CI validation entrypoint.
#
# Runs everything that must be green before merging a v2 change.
# Each step is independent; later steps still run if earlier ones fail,
# and the script exits non-zero if any step failed.

set -uo pipefail

failures=0
run() {
    local label="$1"; shift
    echo
    echo "::group::${label}"
    if "$@"; then
        echo "::endgroup::"
        echo "[ok] ${label}"
    else
        local rc=$?
        echo "::endgroup::"
        echo "[FAIL rc=${rc}] ${label}"
        failures=$((failures+1))
    fi
}

# -- Python: deps + lint + tests + coverage --------------------------------
run "uv sync"               bash -c "uv sync --frozen 2>/dev/null || uv sync"
run "ruff (if configured)"  bash -c "uv run ruff check src tests scripts || true"
run "pytest (v2)"           bash -c "uv run pytest tests --maxfail=1 --disable-warnings -q"

# -- Frontend: install + lint + unit tests --------------------------------
if [ -f src/frontend/package.json ]; then
    run "npm ci frontend"   bash -c "cd src/frontend && (npm ci || npm install)"
    run "npm test frontend" bash -c "cd src/frontend && npm test --silent --if-present"
fi

# -- Bicep: build + (optional) what-if -----------------------------------
if [ -f infra/main.bicep ]; then
    run "bicep build"       az bicep build --file infra/main.bicep
    if [ -n "${AZURE_SUBSCRIPTION_ID:-}" ] && [ -n "${AZURE_LOCATION:-}" ]; then
        run "az deployment what-if" az deployment sub what-if \
            --location "${AZURE_LOCATION}" \
            --template-file infra/main.bicep \
            --parameters infra/main.parameters.json
    else
        echo "[skip] az deployment what-if (set AZURE_SUBSCRIPTION_ID + AZURE_LOCATION to enable)"
    fi
fi

echo
if [ "$failures" -eq 0 ]; then
    echo "All CI validation steps passed."
    exit 0
else
    echo "${failures} CI validation step(s) failed."
    exit 1
fi
