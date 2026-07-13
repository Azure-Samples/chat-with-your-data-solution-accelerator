# ADR 0013 — Frontend ships strict TypeScript end-to-end with `.tsx` everywhere

- **Status**: Accepted
- **Date**: 2026-06-02
- **Phase**: Phase 7 close-out (FE conventions refactor U-P7-FE-REFAC-0)
- **Pillar**: Stable Core (frontend layout + type-safety policy)
- **Deciders**: CWYD v2 maintainers
- **Supersedes**: nothing. This ADR ratifies + extends the TypeScript-strictness baseline established when v2 scaffolded React 19 + TS 5.9 + Vite 7 in Phase 1.

## Context

The v2 backend ships with `pyright --strict` and a 0 errors / 0 warnings / 0 informations CI gate. Hard Rule #11 in [`.github/copilot-instructions.md`](../../../.github/copilot-instructions.md) governs the entire type-discipline surface (closed-set string literals → `StrEnum`; `Any` only at SDK boundaries; etc.).

The frontend started Phase 1 with a weaker contract:

- `tsconfig.json` enabled `strict: true`, `noUnusedLocals`, `noUnusedParameters`, `noFallthroughCasesInSwitch`, `isolatedModules`. It did **not** enable `noUncheckedIndexedAccess` or `exactOptionalPropertyTypes`.
- ESLint ran the JS-only ruleset (`@eslint/js` defaults). The TypeScript-aware `@typescript-eslint/strict-type-checked` + `@typescript-eslint/stylistic-type-checked` configs were **not** wired.
- File extensions were mixed: `.ts` for utilities / hooks / API clients / models; `.tsx` for React components. Hard Rule #11 explicitly codified this mixed convention.

Three concrete pain points surfaced as the FE surface grew through Phases 1–7:

1. **`noUncheckedIndexedAccess` would have caught real bugs.** Array index accesses (`messages[i].role`) and `Record<string, X>` lookups (`citationsById[id].title`) were typed as the value type, not `value | undefined`. Two Phase 4–6 turns burned cycles chasing runtime `Cannot read properties of undefined` errors that the flag would have surfaced at compile time.
2. **`exactOptionalPropertyTypes` would have caught contract drift.** Spread-merge of partial props (`<Foo {...defaults} {...overrides} />` where `overrides.x?: string`) silently passed `undefined` into props that the component had typed as `x?: string` (i.e. "absent" — not "present and undefined"). The flag distinguishes the two cases.
3. **The `.ts` / `.tsx` mixed-extension rule is a friction tax.** Every new file requires a per-file decision ("does this need JSX? if yes, `.tsx`; if no, `.ts`"). The decision is reversible at zero cost (rename), which means it carries information but consumes attention at file-creation time. Tooling (Vite, esbuild, Vitest, tsc) treats both extensions identically for compilation — the only consumer of the distinction is the human reader. Most JS-first React projects ship `.tsx` everywhere for this reason.

The Phase 7 FE conventions refactor (`U-P7-FE-REFAC`) was the moment to close the gap between BE strictness and FE strictness, and to remove the per-file extension decision from the conventions surface.

## Decision

The frontend ships **three coordinated changes** as one policy block:

### 1. `tsconfig.json` enables two additional strict flags

```jsonc
{
  "compilerOptions": {
    "strict": true,                       // unchanged (already on)
    "noUnusedLocals": true,               // unchanged
    "noUnusedParameters": true,           // unchanged
    "noFallthroughCasesInSwitch": true,   // unchanged
    "isolatedModules": true,              // unchanged
    "noUncheckedIndexedAccess": true,     // ADDED
    "exactOptionalPropertyTypes": true,   // ADDED
  }
}
```

These two flags are non-negotiable for the v2 FE. They are the closest TS equivalent of `pyright --strict`'s narrowing posture.

### 2. ESLint runs `strict-type-checked` + `stylistic-type-checked`

The ESLint config switches from the JS-only baseline to the type-aware TypeScript ESLint configs:

```ts
// eslint.config.tsx
import tseslint from "typescript-eslint";

export default tseslint.config(
  ...tseslint.configs.strictTypeChecked,
  ...tseslint.configs.stylisticTypeChecked,
  // project-specific overrides...
);
```

`npm run lint` is CI-gated; the FE lint step fails the build on any error. The stylistic ruleset is included so the FE has a single source of truth for code style (replacing ad-hoc per-PR review feedback).

### 3. All first-party FE files under `src/` and `tests/` use `.tsx` regardless of JSX content

| Path | Extension |
|---|---|
| `src/api/admin.tsx` | `.tsx` (no JSX) |
| `src/models/admin.tsx` | `.tsx` (no JSX) |
| `src/utils/sanitize.tsx` | `.tsx` (no JSX, hypothetical) |
| `src/hooks/useSpeechRecognition.tsx` | `.tsx` (no JSX in some hooks) |
| `src/components/Header/Header.tsx` | `.tsx` (has JSX) |
| `tests/setup.tsx` | `.tsx` (no JSX) |

**Carve-out: tooling configs stay at their tool-pinned names.** `vite.config.ts`, `tsconfig.json`, `tsconfig.node.json`, `eslint.config.tsx`-or-`.ts` (whichever the tool resolves), and any other config files Vite / TypeScript / ESLint / Vitest resolve by exact name are left at the names those tools expect. The carve-out applies to **configs at the package root** — once a file lives under `src/` or `tests/`, the `.tsx` rule applies without exception.

## Consequences

### Positive

- **Real bugs surface at compile time.** `noUncheckedIndexedAccess` catches the entire class of array / record index bugs that produced two Phase 4–6 incident turns. `exactOptionalPropertyTypes` catches contract drift from `undefined` masquerading as "absent."
- **Single source of truth for code style.** ESLint `strict-type-checked` + `stylistic-type-checked` replace ad-hoc PR review feedback; new contributors learn the FE rules from `npm run lint`, not from review history.
- **Symmetric strictness posture with the backend.** `pyright --strict` (BE) and `tsc --strict` + `noUncheckedIndexedAccess` + `exactOptionalPropertyTypes` + ESLint strict (FE) are the two halves of the same policy. The repository now has one type-safety story, not two.
- **No per-file extension decision.** Every first-party FE file is `.tsx`. Contributors stop asking "does this need JSX? if not, should it be `.ts`?" The mental cost drops to zero.
- **Easier rename later.** When a `.tsx` file gains JSX, no rename is needed. When a `.tsx` file loses JSX, no rename is needed. The extension is invariant under the file's content shape.

### Negative

- **One-time fix-up pass.** Enabling the two strict flags will produce a finite set of type errors that must be fixed before CI passes again. Enabling ESLint `strict-type-checked` will produce a finite set of lint errors. Both are mechanical and bounded by the current FE LOC.
- **`.ts` → `.tsx` rename across the FE tree.** ~30 files renamed; vite + tsc handle either extension, so no runtime change. Git history is preserved across renames.
- **Three sibling refactor turns** (`U-P7-FE-REFAC-2` rename, `U-P7-FE-REFAC-3` strict flags, `U-P7-FE-REFAC-4` ESLint) instead of one. Acceptable per Hard Rule #1 (one unit per turn). Each lands green on its own.

### Neutral

- **Stylistic rules from `stylistic-type-checked` may surface preference disagreements.** Mitigation: accept the defaults and override only with a documented rationale per override.
- **`@ts-expect-error` / `@ts-ignore` need a paired comment.** ESLint `strict-type-checked` forbids unexplained suppressions. Each suppression must cite the SDK boundary or framework constraint that forced it — same discipline Hard Rule #11 already imposes on `# pyright: ignore` in the backend.
- **CI cost of type-aware ESLint is non-zero.** `strict-type-checked` runs the TypeScript program to power the type-aware rules. The cost is bounded by the FE LOC and is acceptable for the bug-catching benefit.

## Alternatives considered

1. **Enable only `strict: true`; keep `noUncheckedIndexedAccess` + `exactOptionalPropertyTypes` off.** Rejected — exactly the status quo that produced the two Phase 4–6 incidents. The cost of *not* enabling them is paid by the next contributor who debugs an indexed-access undefined error.
2. **Enable ESLint `recommended-type-checked` instead of `strict-type-checked`.** Rejected — `recommended` is a weaker ruleset chosen for incremental adoption in existing JS-heavy codebases. v2 FE is greenfield TS; `strict` is the matching tier.
3. **Keep the `.ts` / `.tsx` mixed-extension rule.** Rejected — the per-file decision has a non-zero attention cost and a zero behavioral benefit (compilation, bundling, and resolution are all extension-agnostic for first-party FE code).
4. **Migrate to `.ts` everywhere (drop `.tsx` even for components).** Rejected — TypeScript still requires `.tsx` for files containing JSX. The choice is between mixed extensions and `.tsx` everywhere; `.ts` everywhere isn't on the table.
5. **Adopt Biome instead of ESLint + Prettier.** Out of scope. v2 FE shipped with ESLint in Phase 1; switching toolchains is a separate decision that this ADR does not pre-empt. If a future ADR proposes Biome, the type-aware-strict requirement carries forward to the new toolchain (matching ruleset, equivalent enforcement).

## References

- [`.github/copilot-instructions.md`](../../../.github/copilot-instructions.md) Hard Rule #11 — TypeScript naming + extension conventions (this ADR is the consuming policy referenced from the Hard Rule).
- [`.github/instructions/v2-frontend.instructions.md`](../../../.github/instructions/v2-frontend.instructions.md) `## Conventions` section — codifies the three strict flags + ESLint + `.tsx`-everywhere rule from this ADR.
- [`v2/src/frontend/tsconfig.json`](../../src/frontend/tsconfig.json) — the file `U-P7-FE-REFAC-3` amends to add the two new flags.
- [`v2/src/frontend/vite.config.ts`](../../src/frontend/vite.config.ts) — `setupFiles` updated to `./tests/setup.tsx` in `U-P7-FE-REFAC-2`.
- [ADR 0011](0011-frontend-model-extraction.md) — companion FE-layout ADR (wire shapes + domain state types live under `src/models/`).
- [ADR 0012](0012-frontend-test-folder-mirror.md) — companion FE-layout ADR (tests live under `tests/` mirror tree).
- [`development_plan.md`](../development_plan.md) `U-P7-FE-REFAC` debt row — tracks the refactor turns that land this ADR.
