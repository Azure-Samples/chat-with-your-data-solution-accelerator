---
description: "CWYD v2 React/Vite frontend conventions. Use when: editing v2/src/frontend/**, adding a page, adding a component, wiring the API client, calling a service, adding a Registry-backed factory, defining a closed-set enum, consuming the SSE reasoning stream, adding a Context/useReducer store, adding a plugin slot, branding the UI, or merging admin pages."
applyTo: "v2/src/frontend/**"
---

# v2 Frontend (React + Vite) Conventions

## Stack

- React 19, TypeScript 5.9+, Vite 7+.
- **Fluent UI v9** (`@fluentui/react-components` + `@fluentui/react-icons`) is the bundled component library. The MACAE re-skin (dev_plan task #34) committed the decision; new components consume Fluent primitives unless a CSS-Modules-only carve-out is explicitly justified.
- **State management: React Context + `useReducer`.** Lightweight, zero new dep, idiomatic for the reasoning-channel fan-out. Reducers live next to their Context (chat) or page (admin) — do **not** extract reducers into `services/`. Revisit (e.g. Zustand, Redux Toolkit) only if cross-page state grows beyond what context comfortably handles.
- **Routing: `react-router-dom` v7.** `App` mounts `<BrowserRouter>`; the active page is derived from the URL by `pathToSection(location.pathname)` and navigation goes through `useNavigate()` + the `SectionPath` map (`src/models/sections.tsx`). Deep links to `/admin/*` are first-class.
- Testing: Vitest + Testing Library. Tests live under `v2/src/tests/frontend/` mirroring `src/` (relocated from `v2/src/frontend/tests/` per ADR 0020).

## API layer (`src/api/`)

- One typed fetch wrapper per endpoint, one file per backend domain (`api/admin.tsx`, `api/feedback.tsx`, `api/speech.tsx`, `api/streamChat.tsx`). Functions take typed args, return typed responses, throw on non-2xx. **No generated OpenAPI client** — wrappers are hand-rolled. If/when generation lands, the contract above changes via a separate ADR.
- Every wrapper reads `import.meta.env.VITE_BACKEND_URL` at call time so docker-compose / standalone-frontend profiles both work.
- API wrappers do **wire I/O only** — no validation, no optimistic-update orchestration, no dispatch. That belongs in `src/services/` (see below).
- API wrappers are imported by `src/services/**` modules and by tests. **Components do not import from `src/api/` directly** — they call services, which call the API layer.

## Services layer (`src/services/`)

- Services own everything between the API wrapper and the component: orchestration (multi-step flows), validation, derived-state selectors, optimistic-update + rollback flows, SSE stream consumption, and registry wiring. Pages are render-only shells that read state from a Context / `useReducer` and dispatch actions — they never call `fetch`, never compose multi-step flows inline, never declare validation rules in JSX.
- Folder layout: `src/services/<domain>/<service>.ts` (e.g. `services/chat/feedbackService.ts`, `services/admin/ingestService.ts`). Cross-domain primitives live under `src/services/core/` (e.g. the generic `Registry<T>`); app-shell concerns live under `src/services/app/` (e.g. `pageRegistry`, `healthService`).
- Services are **pure TypeScript modules** — no React imports, no hooks. A service signature typically takes the data it needs plus the reducer's `dispatch` and returns `Promise<void>` or a typed result. This keeps services trivially testable and reusable across pages.
- **Reducers stay co-located** with their Context (chat) or page (admin). Moving reducers into services inverts React's state-machine-next-to-its-consumer pattern.
- Tests live under `v2/src/tests/frontend/services/**` mirroring the source tree.

## Factory registries

- The frontend mirrors the backend `Registry[T]` pattern (`backend/core/registry.py`). The generic `Registry<T>` lives at `src/services/core/registry.ts` and exposes `register(key, factory)`, `get(key)`, `has(key)`, and `keys()`. `register` throws on duplicate keys; `get` throws on unknown keys with a message listing every registered key.
- Use a registry **only for genuinely pluggable concerns** — today that is: page rendering by `Section` (`services/app/pageRegistry.tsx`), SSE channel dispatch by `StreamChannel` (`services/chat/channelHandlerRegistry.ts`), and admin form field validation by spec key (`services/admin/validatorFactory.ts`). Do not invent a registry for a `switch` you'll write once and never extend.
- Each registry exports a singleton instance plus its `register`-time side-effect imports (matches the backend `__init__.py` discipline by analogy — a registry module exposes the singleton and the eager registrations, never bare helpers).
- Adding a new value to a registry-backed domain is a single-file change: extend the enum, add a registration call, add a test that the registry resolves the new key.

## Enums (closed-set discriminators)

- Every closed-set string literal in the frontend (nav sections, SSE channels, message roles, reducer action types, status states, theme names) is an `as const` map paired with a literal-union type — the TypeScript counterpart to Python `StrEnum` (Hard Rule #11). **Do not** use the TypeScript `enum` keyword (reverse-mapping pollution, numeric/string ambiguity, tree-shaking edge cases).
- Canonical pattern:
  ```ts
  export const Section = {
    Chat: "chat",
    AdminIngest: "admin-ingest",
    AdminDelete: "admin-delete",
    AdminConfig: "admin-config",
  } as const;
  export type Section = (typeof Section)[keyof typeof Section];
  ```
  Consumers reference `Section.Chat` at call sites; the type narrows to the union `"chat" | "admin-ingest" | ...` so wire payloads, route IDs, and storage keys round-trip without `as` casts. `Object.values(Section)` gives the runtime set for `KNOWN_*` registries and validators.
- Enum locations by scope:
  - **Domain enums** (`StreamChannel`, `MessageRole`) stay in `src/models/<domain>.tsx` next to the wire shapes that consume them.
  - **App-shell enums** (`Section`, `Theme`) live in their own model file (`src/models/sections.tsx`, `src/theme/themeContext.tsx`).
  - **Shared status enums** (`LoadStatus`, `SaveStatus`, `SubmitStatus`, `ReprocessStatus`, `RowDeleteStatus`) live in `src/models/status.tsx` and are imported by every page that needs them — do not redeclare `"loading" | "loaded" | "failed"` locally.
  - **Reducer action types** are an `as const` map next to the reducer (e.g. `ChatActionType` in `pages/chat/ChatContext.tsx`); the `ChatAction` discriminated union references `ChatActionType.Add` etc., never the bare string.

## Plug-and-play surface

- Plugin slots are deferred. When they land, they will be a `Registry<ComponentType>` keyed by a `PluginSlot` enum, registered by integrators via `pluginRegistry.register(slot, component)`. Slot inventory will live in `src/services/app/pluginRegistry.ts` and be re-exported from a `<PluginHost slot={slot} />` component.
- Until then, the page registry (`services/app/pageRegistry.tsx`) is the only registry external integrators may extend without a code change to the core shell.

## SSE consumption (reasoning channel)

- `src/api/streamChat.tsx` exposes `streamChat(messages)` as a typed `AsyncIterable<StreamEvent>` over POST `/api/conversation`. It validates each frame's `channel` against `Object.values(StreamChannel)` at the parse boundary so unknown channels never reach a handler.
- Event fan-out is driven by `services/chat/channelHandlerRegistry.ts` (a `Registry<ChannelHandler>` keyed by the `StreamChannel` enum). Each handler receives `(event, dispatch, messageId)` and emits one or more `ChatAction` dispatches. Adding a new channel is: extend `StreamChannel` → register a handler → write a test — no `switch` to grow.
- The chat page renders (driven by the handlers above):
  - `answer` events → message body via `append_answer`.
  - `reasoning` events → collapsible reasoning panel via `append_reasoning`.
  - `tool` events → step indicators (TBD; currently logged).
  - `citation` events → footnote list via `append_citation`.
  - `error` events → inline `role="alert"` notice via `set_error`; the iterator emits `finish_stream` on completion.

## Stores (Context + useReducer)

- One context per domain: `ChatContext`, `HistoryContext`, `AdminContext`, `SettingsContext`.
- Each context lives under `src/pages/<domain>/` (or `src/state/` for cross-page contexts) and exports a `<XProvider>` plus a `useX()` hook that throws if used outside its provider.
- State is updated through a single `useReducer` per context — actions are typed unions, no setter sprawl.
- No cross-context imports. Cross-domain state goes via prop drilling at the page boundary or, when warranted, a thin `AppContext` composed at `src/main.tsx`.
- If a context starts shouldering large lists or selector-driven re-renders, raise the question in a dedicated turn before reaching for an external state lib.

## Models

- **Wire shapes + domain state types live in `v2/src/frontend/src/models/<domain>.tsx`** — one file per backend domain module. `models/admin.tsx` mirrors `backend/models/admin.py`; `models/chat.tsx` mirrors the conversation + history wire shapes; `models/speech.tsx` mirrors the speech wire shapes; `models/feedback.tsx` mirrors the feedback wire shapes. Models declare nothing else — no helpers, no constants, no React. Rationale + ADR: [v2/docs/adr/0011-frontend-model-extraction.md](../../v2/docs/adr/0011-frontend-model-extraction.md).
- **Inline carve-outs:** component prop interfaces (e.g. `HeaderProps`, `ChatPageProps`, `FeedbackButtonsProps`), hook-shape interfaces (e.g. `UseSpeechRecognition`), and reducer action-union types stay next to their consumer. These are local contracts, not wire / domain shapes.
- **Imports go through the models barrel paths, not inline duplicates.** Once a shape lives in `models/<domain>.tsx`, do not redeclare it at the call site or in the API client — `import type { AdminStatus } from "@/models/admin";` is the only correct form.

## Routing

- **`react-router-dom` v7.** `App` mounts `<BrowserRouter>`; `AppShell` renders a `<Routes>` block — one `<Route>` per `Section` (admin pages mounted as nested `/admin/*` routes under a shared admin layout), plus a `path="*"` catch-all that `<Navigate>`s to `SectionPath[Section.Chat]`. There is no page registry and no `view === "…" && <Page />` ternary chain.
- The active section is **derived from the URL**: `view = pathToSection(location.pathname)`. The `<Header>` nav calls `onSelectView(Section.X)`, which `AppShell` maps to `navigate(SectionPath[X])`. The `Section` ↔ URL mapping lives in `src/models/sections.tsx`.
- Admin pages live under `src/pages/admin/`, mounted as nested routes behind a shared `AdminLayout` (`<Outlet/>` + admin sub-nav). They are part of the same SPA — no separate Streamlit, ever.
## Conventions

- TypeScript strictness: `strict: true`, `noUncheckedIndexedAccess: true`, `exactOptionalPropertyTypes: true`. The three flags are non-negotiable — `tsconfig.json` is the single source of truth. Rationale + ADR: [v2/docs/adr/0013-frontend-strict-ts-and-tsx-everywhere.md](../../v2/docs/adr/0013-frontend-strict-ts-and-tsx-everywhere.md).
- ESLint runs `@typescript-eslint/strict-type-checked` + `@typescript-eslint/stylistic-type-checked` on `src/**` and the relocated test tree `v2/src/tests/frontend/**`. `npm run lint` is CI-gated by [`.github/workflows/v2-frontend-checks.yml`](../workflows/v2-frontend-checks.yml) (lint → typecheck → vitest, all hard-gated, path-scoped to `v2/src/frontend/**` + `v2/src/tests/frontend/**`); any error fails the PR build. Rationale + ADR: [v2/docs/adr/0014-frontend-ci-workflow.md](../../v2/docs/adr/0014-frontend-ci-workflow.md).
- File extension: all first-party files under `src/` and the test tree `v2/src/tests/frontend/` use `.tsx`, regardless of JSX content. Tooling configs (`vite.config.ts`, `tsconfig.json`, `tsconfig.app.json`) stay at their tool-pinned names. See [Hard Rule #11](../copilot-instructions.md) + ADR 0013 above.
- Cross-folder imports under `src/**` and the test tree `v2/src/tests/frontend/**` use the `@/*` path alias (registered in `vite.config.ts` `resolve.alias` and `tsconfig.json` `compilerOptions.paths`). Sibling `./X` imports stay relative — the alias is for cross-folder reach, not for replacing every relative import. Parent-relative imports (`../X`, `../../X`, …) in first-party source/test files are forbidden by ESLint's built-in `no-restricted-imports` with a `^\.\./` regex pattern on the import source string (tool configs like `vite.config.ts` / `tsconfig.json` may still reference `../tests/frontend`). Rationale + ADR: [v2/docs/adr/0015-frontend-path-alias-cross-folder-imports.md](../../v2/docs/adr/0015-frontend-path-alias-cross-folder-imports.md).
- No `any`. Use `unknown` + type narrowing.
- Plain CSS Modules (`*.module.css`) for component styling — no global CSS leaks. If a UI library is later adopted, prefer its idiomatic styling primitive (e.g. Fluent UI `makeStyles`) over CSS Modules for new components in that library's scope.
- **Tests live under `v2/src/tests/frontend/`, mirroring the `src/` tree** (e.g. `src/pages/chat/ChatPage.tsx` → `v2/src/tests/frontend/pages/chat/ChatPage.test.tsx`). Every new component ships with a corresponding `<Component>.test.tsx` under the mirror tree covering at least one behavioral assertion. **Do not colocate `*.test.tsx` next to source files.** The Vitest `include` glob in `vite.config.ts` scans `../tests/frontend/**` only, so colocated tests under `src/` are silently skipped. The `@/*` alias still resolves to `src/`, so test imports of production code are unchanged by the relocation. Rationale + ADR: [v2/docs/adr/0020-frontend-tests-under-src-tests-frontend.md](../../v2/docs/adr/0020-frontend-tests-under-src-tests-frontend.md) (supersedes [ADR 0012](../../v2/docs/adr/0012-frontend-test-folder-mirror.md)).
## Branding / customization

- All branding text/logo loaded at runtime from `/api/admin/ui-config` (backed by `active.json`). *(That endpoint lands in Phase 5 — dev_plan task #35. Until then, the placeholder shell may use a single hard-coded title; replace it the moment the endpoint exists.)*
- Do not hardcode "Chat With Your Data" in components once the config endpoint exists — use the config.
