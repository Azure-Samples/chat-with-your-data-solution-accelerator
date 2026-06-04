# ADR 0015 — Frontend cross-folder imports go through the `@/*` path alias

- **Status**: Accepted
- **Date**: 2026-06-03
- **Phase**: Phase 7 close-out (FE conventions refactor follow-up, U-FE-REVIEW-0b → 0d)
- **Pillar**: Stable Core (frontend layout + import policy)
- **Deciders**: CWYD v2 maintainers
- **Supersedes**: nothing. This ADR ratifies + extends the FE layout conventions established in [ADR 0011](0011-frontend-model-extraction.md), [ADR 0012](0012-frontend-test-folder-mirror.md), [ADR 0013](0013-frontend-strict-ts-and-tsx-everywhere.md), and [ADR 0014](0014-frontend-ci-workflow.md).

## Context

The v2 FE layout established by ADRs 0011/0012/0013 produced a deep, predictable folder tree: `src/{api,components,hooks,models,pages,services,theme}/**` with `tests/` mirroring it. The deepest test, `tests/pages/chat/components/CitationPanel/CitationPanel.test.tsx`, sits 5 directories below the FE package root.

Through Phases 1–7 the FE acquired ~50 cross-folder imports written as parent-relative paths. The depth ranged from `../api/speech` (one level up) to `../../../../../src/models/chat` (five levels up). Three pain points surfaced:

1. **Readability cost grows with depth.** `import type { Citation } from "../../../../../src/models/chat"` requires the reader to count `..` segments to know which folder the import resolves into. The path encodes *distance from the importer*, not *what is being imported*. A reader who knows the FE layout still has to mentally re-anchor on every import.
2. **Refactors break paths in noisy ways.** Moving `pages/chat/components/MessageInput.tsx` one level up (or down) rewrites every parent-relative import in the file *and* every import that targets the file. Git diffs balloon with churn that has nothing to do with the intent of the move. The friction discourages otherwise-good restructures.
3. **MACAE shipped the `@/*` alias already.** The Multi-Agent Custom Automation Engine accelerator (a read-only architectural reference per `.github/copilot-instructions.md`) uses a single `@/*` → `src/*` alias for every cross-folder import. The convention is established, idiomatic Vite + TS, and proven across MACAE's full FE surface.

A convention rules update alone wasn't enough. Without lint enforcement, the next contributor — or future-us in a different branch — would silently re-introduce `../../models/chat`, and within a few PRs the alias discipline would rot. The convention had to ship with a hard wall.

The FE-REVIEW work stream (`plan-fe-review.md`) was the moment to (a) wire the alias into Vite + TS, (b) migrate every source-side + test-side parent-relative cross-folder import to the alias, and (c) lock the convention in with an ESLint rule. Units `U-FE-REVIEW-0b` (alias infra) → `0c-A` → `0c-B` → `0c-C` → `0c-D` → `0c-E` landed the migration; `U-FE-REVIEW-0d` lands the lint rule.

## Decision

The frontend ships **four coordinated changes** as one policy block:

### 1. `vite.config.ts` registers the alias

```ts
import { fileURLToPath, URL } from "node:url";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  // ...
});
```

The ESM-style `fileURLToPath(new URL(..., import.meta.url))` is the Vite 7 idiom for path resolution that works without `__dirname`. This single block covers dev (`vite`), build (`vite build`), and test (`vitest run`) because the v2 FE inlines Vitest config inside `vite.config.ts` rather than maintaining a separate `vitest.config.ts`.

### 2. `tsconfig.json` registers the path mapping

```jsonc
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["src/*"]
    }
  }
}
```

This makes `tsc --noEmit` resolve the alias the same way Vite does at runtime, so type-checking matches build behavior. ESLint's `@typescript-eslint/strict-type-checked` config picks the paths up automatically via `projectService: true` — no plugin work needed for type-aware lint rules.

### 3. All cross-folder imports under `src/**` and `tests/**` use the alias

```ts
// Cross-folder reach — always uses the alias.
import type { Citation } from "@/models/chat";
import { streamChat } from "@/api/streamChat";
import { useSpeechRecognition } from "@/hooks/useSpeechRecognition";

// Sibling imports — stay relative. The alias is for cross-folder
// reach, not for replacing every relative import.
import { CitationCard } from "./CitationCard";
import styles from "./CitationPanel.module.css";

// Cross-folder reach in a sibling subtree — alias, not ../X.
import { useChatContext } from "@/pages/chat/ChatContext";
```

The sibling-`./X` carve-out is intentional. `./CitationCard` reads cleaner than `@/pages/chat/components/CitationPanel/CitationCard` and the relative form correctly encodes the design relationship ("these two files are siblings — they belong together"). Aliasing siblings would add noise without adding information.

### 4. ESLint forbids parent-relative imports

```js
// eslint.config.js
export default tseslint.config(
  {
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              regex: "^\\.\\./",
              message: "Cross-folder imports must use the '@/' path alias (see ADR 0015). Sibling './X' imports are allowed.",
            },
          ],
        },
      ],
    },
  },
  // ...
);
```

ESLint's built-in `no-restricted-imports` rule with a regex pattern fires on any import whose source text starts with `../`. Sibling `./X` and aliased `@/X` paths pass because the rule checks the **source string**, not the **resolved filesystem path** — which is the correct shape: we want `@/models/chat` to pass even though it resolves to a parent directory under `src/`. `npm run lint` is already CI-gated by [ADR 0014](0014-frontend-ci-workflow.md), so the rule is build-breaking from the moment it lands. No plugin or resolver is required.

## Consequences

### Positive

- **Paths describe *what*, not *distance to what*.** `import { CitationPanel } from "@/pages/chat/components/CitationPanel/CitationPanel"` tells the reader exactly which file the import targets, regardless of where the importer lives. No `..` counting.
- **Refactors stop churning import paths.** Moving a file changes only that file's *sibling* imports (intentionally — siblings stay relative). All cross-folder imports targeting the file remain correct because they're absolute under `@/*`. Git diffs for restructures shrink dramatically.
- **Convention enforced at lint, not by discipline.** Without the lint rule, the alias migration would be a one-time win that decays. With the rule, the next `../../models/chat` someone writes fails CI before it can land. The convention is permanent.
- **Symmetric with MACAE.** Anyone moving between MACAE and CWYD FE work sees the same import convention. Cross-pollination of contributors costs nothing.

### Negative

- **One-time migration cost.** ~50 import sites across `src/**` + `tests/**` had to be rewritten. The cost is paid (units `0c-A` → `0c-E` are complete) and bounded.
- **No type-aware import-graph rules today.** Choosing the built-in `no-restricted-imports` (rather than `eslint-plugin-import`) means we don't get rules like `import/no-cycle` or `import/order` for free. If those become valuable we revisit; for the cross-folder-alias enforcement at hand, the zero-plugin path is strictly simpler.

### Neutral

- **Sibling `./X` carve-out preserved.** Imports targeting files in the same folder stay relative, by design. Any future move to "alias everything" would need a separate ADR.
- **Single alias, not many.** This ADR commits to one alias (`@/` → `src/`). A future ADR could split into `@models/`, `@api/`, etc. if the FE surface grows large enough to warrant per-domain aliasing. Today, the single alias keeps `tsconfig` paths simple and matches MACAE exactly.
- **Test files mirror the rule.** `tests/**` follows the same alias rule as `src/**` — both use `@/pages/...` to reach into source code. The mirror layout ([ADR 0012](0012-frontend-test-folder-mirror.md)) means tests are deep, so they benefit most from the alias.

## Alternatives considered

1. **Leave deep relatives in place.** Rejected — the observed pain (readability + refactor churn) is concrete, and the migration cost is bounded. Doing nothing is the most expensive option over the FE's remaining lifetime.
2. **Migrate to alias but skip the lint rule.** Rejected — conventions enforced only by discipline rot silently. One re-introduced `../models/chat` per quarter would leave the FE half-aliased within a year, which is worse than either extreme.
3. **Multiple per-domain aliases (`@models/*`, `@api/*`, `@components/*`, ...).** Rejected for now. Single `@/*` matches MACAE, keeps `tsconfig.paths` simple, and the explicit folder segment in `@/models/chat` already carries the "what folder" cue. Per-domain aliases would add a second layer of mental indirection ("is `@models/chat` even a thing? oh yes, mapped to `src/models/`") for zero readability gain over `@/models/chat`.
4. **Alias siblings too (drop `./X` carve-out).** Rejected — sibling imports correctly encode "these files belong together" by being relative. `./CitationCard` is shorter and clearer than `@/pages/chat/components/CitationPanel/CitationCard` for code that *already lives in that folder*.
5. **Use Node 22's import maps / package `exports`.** Out of scope. Vite + TS path mapping is the established Vite-ecosystem approach; package `exports` is for publishing distinct subpaths from a published package, which the FE is not.
6. **Migrate to a router with route-relative imports (e.g. Remix file-based routing).** Out of scope. The FE has no router today ([instructions/v2-frontend.instructions.md](../../../.github/instructions/v2-frontend.instructions.md) `## Routing`); introducing one is its own decision. The alias works whether or not a router lands later.
7. **Use `import/no-relative-parent-imports` from `eslint-plugin-import`.** Rejected after trying it. The rule checks the **resolved filesystem path** of every import, not the **source text**. With the TS resolver wired up, `@/pages/chat/components/answerTokens` resolves to `src/pages/chat/components/answerTokens.tsx` — which is a parent directory relative to the importing test file — so the rule flags every aliased import as a false positive. The built-in `no-restricted-imports` with a regex on the source string is the correct shape for what we actually want to enforce, and it eliminates two devDeps in the process.

## References

- [`.github/copilot-instructions.md`](../../../.github/copilot-instructions.md) — Hard Rule #11 governs naming conventions; this ADR governs a tooling convention (import paths), which is adjacent but distinct.
- [`.github/instructions/v2-frontend.instructions.md`](../../../.github/instructions/v2-frontend.instructions.md) `## Conventions` section — codifies the alias rule + the lint enforcement from this ADR.
- [`v2/src/frontend/vite.config.ts`](../../src/frontend/vite.config.ts) — registers `resolve.alias` (landed in `U-FE-REVIEW-0b`).
- [`v2/src/frontend/tsconfig.json`](../../src/frontend/tsconfig.json) — registers `paths` mapping (landed in `U-FE-REVIEW-0b`).
- [`v2/src/frontend/eslint.config.js`](../../src/frontend/eslint.config.js) — `no-restricted-imports` rule with `^\.\./` regex pattern (lands in `U-FE-REVIEW-0d`).
- [ADR 0011](0011-frontend-model-extraction.md) — model extraction (the folder layout the alias resolves into).
- [ADR 0012](0012-frontend-test-folder-mirror.md) — mirror-tree tests (the deepest consumers of cross-folder imports).
- [ADR 0013](0013-frontend-strict-ts-and-tsx-everywhere.md) — strict TS posture (the lint config this ADR extends).
- [ADR 0014](0014-frontend-ci-workflow.md) — CI workflow (the gate that makes the lint rule build-breaking).
- MACAE — the read-only architectural reference whose `@/*` alias pattern this ADR adopts.
