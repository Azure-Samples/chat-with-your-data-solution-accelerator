# ADR 0029 — Frontend tests live under `v2/tests/frontend/` (symmetric with backend; relocated from `v2/src/tests/frontend/`)

- **Status**: Accepted
- **Date**: 2026-06-20
- **Phase**: Post-Phase-7 (test-layout symmetry)
- **Pillar**: Stable Core (frontend layout policy)
- **Deciders**: CWYD v2 maintainers (repo-owner decision)
- **Supersedes**: [ADR 0020](0020-frontend-tests-under-src-tests-frontend.md) (and, transitively, [ADR 0012](0012-frontend-test-folder-mirror.md))

## Context

[ADR 0020](0020-frontend-tests-under-src-tests-frontend.md) placed the frontend TypeScript/Vitest test tree under `v2/src/tests/frontend/` to realize a single `v2/src/tests/` root. It explicitly **accepted the asymmetry** with the backend test tree (`v2/tests/backend/`) as a tradeoff, and recorded the symmetric option — `v2/tests/frontend/` — as its **alternative #2**, "the symmetric option if the asymmetry above is ever revisited."

The repo owner has now revisited it and chosen symmetry: all test trees live under the top-level `v2/tests/<area>/` root, so the frontend Vitest tree sits at `v2/tests/frontend/`, matching `v2/tests/backend/`, `v2/tests/functions/`, `v2/tests/infra/`, etc. There is no longer any `v2/src/tests/` directory.

The Python ASGI test for the frontend's static-file server previously sat at `v2/tests/frontend/test_frontend_app.py`. To keep each test directory **single-toolchain** (Vitest vs pytest), that pytest file moves to `v2/tests/frontend_app/test_frontend_app.py`, so the Vitest tree owns `v2/tests/frontend/` cleanly.

The mirror-tree shape and the no-colocation invariant from ADR 0012 / ADR 0020 are **kept** — only the test-tree *root* moves, from `v2/src/tests/frontend/` to `v2/tests/frontend/`.

## Decision

**Frontend TypeScript/Vitest tests live under `v2/tests/frontend/`, mirroring `v2/src/frontend/src/`. Colocating `*.test.tsx` next to source files under `src/` remains forbidden.**

Concretely:

1. For every file `v2/src/frontend/src/<path>.tsx` that ships a test, the test path is `v2/tests/frontend/<path>.test.tsx`.
2. The test tree stays a self-contained npm workspace member (`cwyd-frontend-tests`) with its own `vitest.config.ts`, `tsconfig.json`, and `eslint.config.js`. The package **name** is unchanged, so every `--workspace cwyd-frontend-tests` script keeps working.
3. The `@/*` alias still resolves to the frontend source (`v2/src/frontend/src/*`). Only the **relative** path from the test package changes — `../../frontend/src` → `../../src/frontend/src` — in the test package's `vitest.config.ts` and `tsconfig.json`. Test files import production code via `@/...`, so **no per-file import rewrite is needed**.
4. The frontend's Python ASGI test moves to `v2/tests/frontend_app/test_frontend_app.py`, keeping `v2/tests/frontend/` Vitest-only. Its `Path(__file__).resolve().parents[2]` anchor still resolves to `v2/` at the new depth, so the test body is unchanged.

### Build / tooling mechanics

- **npm workspace root.** `v2/package.json` members become `src/frontend` (`cwyd-frontend`) and `tests/frontend` (`cwyd-frontend-tests`). A single `npm ci` at `v2/` still hoists one shared `v2/node_modules`. `package-lock.json` is regenerated for the new member path.
- **CI.** `.github/workflows/v2-frontend-checks.yml` path filters and the `npx tsc -p tests/frontend` step use the new path; the `npm run lint` / `npm test` steps are unchanged (they delegate by package name).
- **Docker.** `Dockerfile.frontend` copies only `src/frontend` and builds the frontend package standalone, so the production image is **unaffected** by the test-tree location; only a stale comment was updated.

## Consequences

### Positive

- **Symmetric test layout.** All test trees live under `v2/tests/<area>/` (backend, frontend, functions, infra, …). The asymmetry ADR 0020 listed as its primary negative is resolved.
- **Single-toolchain test directories.** `v2/tests/frontend/` is Vitest-only; `v2/tests/frontend_app/` is pytest-only. No mixed-toolchain directory.
- **`@/` alias unchanged ⇒ zero per-test import churn.** Only two config files (the test package's `vitest.config.ts` + `tsconfig.json`) change their relative alias path.

### Negative

- **Second relocation churns history again.** Moving the tree a second time re-touches the same files in `git log`. One-time cost, accepted by the owner for the symmetry payoff.
- **The test tree remains a separate workspace member.** As with ADR 0020, it is its own package (`package.json` + configs) under a workspace root — more moving parts than colocated tests, but the frontend package stays build-only and the production image never references the test tree.

### Neutral

- **No `v2/src/tests/` directory remains.** The frontend source package is `v2/src/frontend/`; the frontend test package is `v2/tests/frontend/`.

## Alternatives considered

1. **Keep ADR 0020 (`v2/src/tests/frontend/`).** Rejected — the owner now prefers symmetry with the backend tree over a single `v2/src/tests/` root.
2. **Co-locate the Vitest tree and the pytest `test_frontend_app.py` in `v2/tests/frontend/`.** Rejected — keep each test directory single-toolchain; the pytest file moves to `v2/tests/frontend_app/` instead.

## References

- [ADR 0020](0020-frontend-tests-under-src-tests-frontend.md) — superseded by this ADR; its mirror-tree + no-colocation decision is retained, its `v2/src/tests/frontend/` root is replaced by `v2/tests/frontend/`.
- [ADR 0012](0012-frontend-test-folder-mirror.md) — transitively superseded (the original mirror-tree decision).
- [ADR 0013](0013-frontend-strict-ts-and-tsx-everywhere.md) — companion FE-layout ADR (`.tsx` everywhere + strict TS); the relocated tests keep `.tsx`.
- [`v2/package.json`](../../package.json) — workspace root; member `tests/frontend`.
- [`.github/workflows/v2-frontend-checks.yml`](../../../.github/workflows/v2-frontend-checks.yml) — frontend CI gate; path-scoped to `v2/src/frontend/**` + `v2/tests/frontend/**`.
- Hard Rule #11 in [.github/copilot-instructions.md](../../../.github/copilot-instructions.md) — TS file-name + `.tsx` rule; its `v2/src/tests/frontend/` reference is updated to `v2/tests/frontend/` alongside this ADR.
