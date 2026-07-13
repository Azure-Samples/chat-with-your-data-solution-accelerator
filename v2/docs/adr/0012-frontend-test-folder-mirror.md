# ADR 0012 — Frontend tests live under `v2/src/frontend/tests/` mirroring the `src/` tree (no colocation)

> **Superseded by [ADR 0020](0020-frontend-tests-under-src-tests-frontend.md) (2026-06-08).** The mirror-tree + no-colocation decision below still holds, but the test-tree root moved from `v2/src/frontend/tests/` to `v2/src/tests/frontend/`. Read ADR 0020 for the current location and the build/tooling mechanics.

- **Status**: Superseded by [ADR 0020](0020-frontend-tests-under-src-tests-frontend.md) (2026-06-08)
- **Date**: 2026-06-02
- **Phase**: Phase 7 close-out (FE conventions refactor U-P7-FE-REFAC-0)
- **Pillar**: Stable Core (frontend layout policy)
- **Deciders**: CWYD v2 maintainers
- **Supersedes**: nothing. This ADR ratifies an existing convention from [v2-frontend.instructions.md](../../../.github/instructions/v2-frontend.instructions.md) so it can be cited by future refactors without re-litigating it.
- **Superseded by**: [ADR 0020](0020-frontend-tests-under-src-tests-frontend.md) — frontend tests relocated from `v2/src/frontend/tests/` to `v2/src/tests/frontend/` (mirror-tree + no-colocation invariants retained).

## Context

Frontend tests in v2 already live under `v2/src/frontend/tests/`, mirroring `src/`:

```
src/api/admin.tsx              → tests/api/admin.test.tsx
src/pages/chat/ChatPage.tsx    → tests/pages/chat/ChatPage.test.tsx
src/components/Header/Header.tsx → tests/components/Header/Header.test.tsx
```

This convention is enforced by `vite.config.ts`:

```ts
test: {
  include: ["tests/**/*.{test,spec}.{ts,tsx}"],
}
```

Any `*.test.tsx` placed next to its source file under `src/` is **silently skipped** by Vitest because the glob doesn't match it. The convention has been in [v2-frontend.instructions.md](../../../.github/instructions/v2-frontend.instructions.md) since Phase 1, but it lives only in the instruction file — no ADR cites it. Three times during Phases 4–6 a contributor (human or agent) proposed colocating tests next to source ("standard React convention"), and each time the convention had to be re-explained from the instruction file.

The Phase 7 FE conventions refactor (`U-P7-FE-REFAC`) revisits FE layout policy in a single coordinated turn. This is the moment to promote the convention from a single-line instruction bullet into a citable ADR, so future refactors can reference it without re-opening the question.

## Decision

**Frontend tests live under `v2/src/frontend/tests/`, mirroring the `src/` tree. Colocating `*.test.tsx` next to source files under `src/` is forbidden.**

Concretely:

1. For every file `v2/src/frontend/src/<path>.tsx` that ships a test, the test file path is `v2/src/frontend/tests/<path>.test.tsx`.
2. The Vitest `include` glob in [`vite.config.ts`](../../src/frontend/vite.config.ts) is `tests/**/*.{test,spec}.{ts,tsx}` and is not widened to scan `src/`. The `src/` tree is application code; the `tests/` tree is test code.
3. Test fixtures, helpers, and stub providers that are imported by `tests/**` files live under `tests/`, not under `src/`. The `src/` tree imports only from other `src/` files.
4. The setup file referenced by `vite.config.ts` `setupFiles` is `./tests/setup.tsx`.

## Consequences

### Positive

- **Single import-graph direction: `tests/` → `src/`, never the reverse.** This makes "what does production ship?" answerable by reading `src/` alone — no test fixtures, no mocks, no setup code in the production tree.
- **`src/` stays uniformly `.tsx` source files.** No interleaved `.tsx` / `.test.tsx` pairs that obscure the directory contents.
- **No "did this test actually run?" silent failures.** A colocated test in `src/` is silently skipped by Vitest; the mirror-tree convention makes the failure mode impossible because tests can't live in a location Vitest doesn't scan.
- **Symmetric with the backend.** Backend production code lives under `v2/src/backend/`, backend tests under `v2/tests/backend/`. Same tree-shape on both sides.

### Negative

- **Two-file navigation for source ↔ test.** Editors that auto-open the test file for the current source file (e.g. VS Code's `Jest > Reveal Test File` command) need a path resolver that knows about the mirror. Standard tooling handles this via convention; not a real cost.
- **A new component requires two file creations in two trees.** Acceptable — and arguably a *feature*, because it makes the test-first rule (every new component ships with a corresponding test) visible at file-creation time.

### Neutral

- **Component prop fixtures and rendering helpers (e.g. `renderWithProviders`) live under `tests/`, not `src/`.** Even though they are "code that supports tests," they are not production code. Putting them under `src/` would let production code accidentally import them.

## Alternatives considered

1. **Colocate tests next to source (`src/api/admin.tsx` + `src/api/admin.test.tsx`).** Rejected — Vitest `include` glob doesn't currently match it, every Phase 1+ FE test file is already under `tests/`, and the import-direction invariant (`tests/` → `src/` only) is more valuable than colocation convenience. The colocation pattern is more common in JS-first React projects, but v2 chose the mirror-tree pattern from Phase 1 and has stuck with it.
2. **Both — colocated OR mirrored.** Rejected — two conventions in the same tree breeds inconsistency; agents and humans both pick whichever is closer at hand.
3. **Move tests up one level to `v2/tests/frontend/`** (parallel to `v2/tests/backend/`). Rejected — the FE has its own package boundary (`v2/src/frontend/package.json`, `v2/src/frontend/vite.config.ts`); tests that belong to that package belong inside it.
4. **Widen the Vitest `include` glob to `{src,tests}/**`** so colocated tests also run. Rejected — solves nothing the current rule doesn't already solve, and creates the failure mode where someone adds a colocated test alongside an existing mirror-tree test and ships duplicate coverage.

## References

- [`.github/instructions/v2-frontend.instructions.md`](../../../.github/instructions/v2-frontend.instructions.md) `## Conventions` section — the line "Tests live under `v2/src/frontend/tests/`, mirroring the `src/` tree" is the existing instruction this ADR promotes to ratified policy.
- [`v2/src/frontend/vite.config.ts`](../../src/frontend/vite.config.ts) `test.include` — the mechanical enforcement glob.
- [ADR 0011](0011-frontend-model-extraction.md) — companion FE-layout ADR (wire shapes + domain state types live under `src/models/`).
- [ADR 0013](0013-frontend-strict-ts-and-tsx-everywhere.md) — companion FE-layout ADR (`.tsx` everywhere + extra strict TS flags).
- [`development_plan.md`](../development_plan.md) `U-P7-FE-REFAC` debt row — tracks the refactor turns that land this ADR.
