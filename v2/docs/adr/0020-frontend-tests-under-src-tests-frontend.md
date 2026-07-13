# ADR 0020 — Frontend tests live under `v2/src/tests/frontend/` (relocated from `v2/src/frontend/tests/`)

> **Superseded by [ADR 0029](0029-frontend-tests-symmetric-under-tests-frontend.md) (2026-06-20).** The mirror-tree + no-colocation decision below still holds, but the test-tree root moved from `v2/src/tests/frontend/` to `v2/tests/frontend/` (symmetric with `v2/tests/backend/`). Read ADR 0029 for the current location and the build/tooling mechanics.

- **Status**: Superseded by [ADR 0029](0029-frontend-tests-symmetric-under-tests-frontend.md)
- **Date**: 2026-06-08
- **Phase**: Post-Phase-7 (PP7 work stream — `U-PP7-RELOC`)
- **Pillar**: Stable Core (frontend layout policy)
- **Deciders**: CWYD v2 maintainers (repo-owner override of [ADR 0012](0012-frontend-test-folder-mirror.md) alternative #3)
- **Supersedes**: [ADR 0012](0012-frontend-test-folder-mirror.md)
- **Superseded by**: [ADR 0029](0029-frontend-tests-symmetric-under-tests-frontend.md) — frontend tests relocated from `v2/src/tests/frontend/` to `v2/tests/frontend/` (symmetric with the backend tree; mirror-tree + no-colocation invariants retained).

## Context

[ADR 0012](0012-frontend-test-folder-mirror.md) ratified frontend tests living under `v2/src/frontend/tests/`, mirroring the `src/` tree, and explicitly **rejected** moving them out of the frontend package (its alternative #3, "move tests up one level to `v2/tests/frontend/`") on the grounds that the frontend owns its own package boundary (`v2/src/frontend/package.json`, `v2/src/frontend/vite.config.ts`).

The repo owner has since asked for a single `v2/src/tests/` test root, with the frontend TypeScript/Vitest tests relocated to `v2/src/tests/frontend/`. This is a deliberate override of ADR 0012's alternative #3: the owner accepts crossing the frontend package boundary in exchange for a predictable `v2/src/tests/<area>/` layout. The mirror-tree shape and the no-colocation invariant from ADR 0012 are **kept** — only the test-tree *root* moves.

The target `v2/src/tests/frontend/` (inside `v2/src/`) is distinct from the `v2/tests/frontend/` path ADR 0012 rejected. The Python ASGI test for the frontend's static-file server (`v2/tests/frontend/test_frontend_app.py`) belongs to the pytest tree and is **unaffected** — only the TypeScript/Vitest tests move.

## Decision

**Frontend TypeScript/Vitest tests live under `v2/src/tests/frontend/`, mirroring `v2/src/frontend/src/`. Colocating `*.test.tsx` next to source files under `src/` remains forbidden.**

Concretely:

1. For every file `v2/src/frontend/src/<path>.tsx` that ships a test, the test path is `v2/src/tests/frontend/<path>.test.tsx`.
2. The test tree is a self-contained npm workspace member (`cwyd-frontend-tests`) with its own [`vitest.config.ts`](../../src/tests/frontend/vitest.config.ts): `include: ["**/*.{test,spec}.{ts,tsx}"]` (its own directory) and `setupFiles: ["./setup.tsx"]`. The frontend package's [`vite.config.ts`](../../src/frontend/vite.config.ts) is build-only and carries no `test` block.
3. The `@/*` path alias is **unchanged** — it still resolves to the frontend source (`v2/src/frontend/src/*`); the test package declares it in its own `vitest.config.ts` and `tsconfig.json` as `../../frontend/src`. Test files keep importing production code via `@/...`, so no per-file import rewrite is needed.
4. Test fixtures, helpers, and stub providers imported by the test tree live under `v2/src/tests/frontend/`, not under `src/`. The import-graph direction stays one-way: tests → `src`, never the reverse.

### Build / tooling mechanics

The relocation pushes tests outside the frontend package directory (`v2/src/frontend/`), which the Docker build copies wholesale (`COPY src/frontend ./`). Rather than have the frontend package reach back out to the external test tree, the tree is its **own npm workspace member**, so each package owns a self-contained toolchain:

- **npm workspace root.** [`v2/package.json`](../../package.json) declares two members — `src/frontend` (`cwyd-frontend`) and `src/tests/frontend` (`cwyd-frontend-tests`). A single `npm ci` at the `v2/` root produces one hoisted `v2/node_modules` shared by both members, so the test package resolves the frontend's runtime deps (React, react-router-dom, Fluent UI) as a **single instance** — no duplicate-React or dual-router-context bugs. The root scripts delegate to the members (`build` → `cwyd-frontend`, `test` → `cwyd-frontend-tests`, `lint` → both).
- **Frontend package stays build-only.** [`vite.config.ts`](../../src/frontend/vite.config.ts) and the single [`tsconfig.json`](../../src/frontend/tsconfig.json) (`include: ["src"]`) describe only the app; neither references the test tree. The production build is `tsc -b && vite build`, and [`Dockerfile.frontend`](../../docker/Dockerfile.frontend) copies only `src/frontend`, so the image build never sees the test tree or the workspace root. There is no `tsconfig.app.json` — the earlier build/editor `tsconfig` split is gone.
- **Test package owns its own config.** `cwyd-frontend-tests` carries its own [`vitest.config.ts`](../../src/tests/frontend/vitest.config.ts), [`tsconfig.json`](../../src/tests/frontend/tsconfig.json) (`@/* → ../../frontend/src/*`, with `include` pulling in `../../frontend/src` for type info), and [`eslint.config.js`](../../src/tests/frontend/eslint.config.js) (the frontend's strict-type-checked preset with the mock / test-double rules relaxed). The `@` alias in both the Vitest and TS config points at `../../frontend/src`, matching the alias the frontend uses internally.

## Consequences

### Positive

- **Single predictable test root (`v2/src/tests/<area>/`).** The owner's target layout — all frontend test trees discoverable under one `v2/src/tests/` parent — is realized.
- **Mirror-tree + no-colocation invariants preserved.** Everything ADR 0012 bought (one-way import graph, uniformly-`.tsx` `src/`, no silently-skipped colocated tests) still holds; only the root moved.
- **`@/` alias unchanged ⇒ zero per-test import churn.** Because every test already imports production code through `@/...`, moving the test root does not touch a single `import` line inside the test files.

### Negative

- **Asymmetry with the backend test tree.** Backend tests live at `v2/tests/backend/` (top-level `v2/tests/`), while frontend tests now live at `v2/src/tests/frontend/` (inside `v2/src/`). This is an owner-accepted tradeoff: the owner prefers a `v2/src/tests/` root for the frontend over symmetry with the backend tree.
- **A second npm package + a workspace root.** Placing tests outside the frontend package means the test tree is its own package (`package.json` + `vitest.config.ts` + `tsconfig.json` + `eslint.config.js`) governed by a workspace root (`v2/package.json`). That is more moving parts than colocated tests, but each package's toolchain is self-contained and the frontend package stays build-only — the production image and its `tsconfig` never reference the test tree.

### Neutral

- **Two "frontend test" locations exist by design.** `v2/src/tests/frontend/**` holds the TypeScript/Vitest tests; `v2/tests/frontend/test_frontend_app.py` holds the Python ASGI test for the static-file server. They belong to different toolchains (Vitest vs pytest) and are intentionally not merged.

## Alternatives considered

1. **Keep ADR 0012 as-is (`v2/src/frontend/tests/`).** Rejected by the repo owner in favor of a unified `v2/src/tests/` root.
2. **Move to `v2/tests/frontend/` (ADR 0012 alternative #3, symmetric with backend).** Not chosen — the owner specifically asked for `v2/src/tests/frontend/` (under `v2/src/`). Recorded here because it remains the symmetric option if the asymmetry above is ever revisited.
3. **Rewrite every test import from `@/...` to relative paths after the move.** Unnecessary — the `@/` alias already insulates test imports from the test tree's location.

## References

- [ADR 0012](0012-frontend-test-folder-mirror.md) — superseded by this ADR; its mirror-tree + no-colocation decision is retained, its `v2/src/frontend/tests/` root is replaced.
- [ADR 0013](0013-frontend-strict-ts-and-tsx-everywhere.md) — companion FE-layout ADR (`.tsx` everywhere + strict TS flags); the relocated tests keep `.tsx`.
- [`v2/package.json`](../../package.json) — the npm workspace root that hoists `node_modules` for both members.
- [`vitest.config.ts`](../../src/tests/frontend/vitest.config.ts) `test.include` / `test.setupFiles` — the test package's own enforcement globs (scan its own tree; `@` → `../../frontend/src`).
- [`Dockerfile.frontend`](../../docker/Dockerfile.frontend) — the production image build; copies only `src/frontend` and runs `tsc -b && vite build`, so it never references the test tree or workspace root.
- Hard Rule #11 in [.github/copilot-instructions.md](../../../.github/copilot-instructions.md) — the TS file-name + `.tsx` rule; its `v2/src/frontend/tests/` reference is updated to `v2/src/tests/frontend/` alongside this ADR.
- [`development_plan.md`](../development_plan.md) §0.0c `U-PP7-RELOC` — tracks the relocation turns that land this ADR.
