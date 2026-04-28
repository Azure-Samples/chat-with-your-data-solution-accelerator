---
description: "CWYD v2 React/Vite frontend conventions. Use when: editing v2/src/frontend/**, adding a page, adding a component, wiring the API client, consuming the SSE reasoning stream, adding a Context/useReducer store, adding a plugin slot, branding the UI, or merging admin pages."
applyTo: "v2/src/frontend/**"
---

# v2 Frontend (React + Vite) Conventions

## Stack

- React 19, TypeScript 5.9+, Vite 7+.
- **No UI component library is bundled by default.** Phase 1 ships a bare scaffold; the UI library decision is deferred to dev_plan task #24 (chat-page SSE wire-up) so the choice is made against real component requirements, not speculative ones.
- **State management: React Context + `useReducer`.** Lightweight, zero new dep, idiomatic for the reasoning-channel fan-out. Revisit (e.g. Zustand, Redux Toolkit) only if cross-page state grows beyond what context comfortably handles — expected earliest in Phase 5 (admin merge).
- **Routing: none in Phase 1.** Add a router (e.g. React Router 7) only when the first multi-page need lands — dev_plan task #36 (admin merged into the chat SPA).
- Testing: Vitest + Testing Library + (optional) MSW for API mocking. Jest remains for files migrated from v1, but new tests use Vitest.

## Plug-and-play surface

- All API calls go through `src/api/client.ts` which reads `import.meta.env.VITE_BACKEND_URL`. (`client.ts` lands in dev_plan task #15.)
- The OpenAPI client is **generated** into `src/api/generated/`. Do not hand-edit. Regenerate via `make openapi` or the pre-commit hook. *(Generation pipeline lands alongside dev_plan task #24; until then `client.ts` may hand-author the small surface it needs.)*
- Plugin slots: a `<PluginHost slot="chat-toolbar" />` component renders any registered plugin for that slot. Custom integrators add plugins via `registerPlugin({slot, component})`. Slots planned: `chat-toolbar`, `message-actions`, `admin-nav`, `reasoning-renderer`. *(`PluginHost` itself is a Phase 5 deliverable — dev_plan task #36.)*

## SSE consumption (reasoning channel)

- `src/api/sse.ts` exposes `useEventStream(url, body)` that yields typed `OrchestratorEvent` objects.
- The chat page renders:
  - `answer` events → message body.
  - `reasoning` events → collapsible "Show reasoning" panel (default collapsed).
  - `tool` events → step indicators.
  - `citation` events → footnote list.
  - `error` events → error toast, close stream.

## Stores (Context + useReducer)

- One context per domain: `ChatContext`, `HistoryContext`, `AdminContext`, `SettingsContext`.
- Each context lives under `src/pages/<domain>/` (or `src/state/` for cross-page contexts) and exports a `<XProvider>` plus a `useX()` hook that throws if used outside its provider.
- State is updated through a single `useReducer` per context — actions are typed unions, no setter sprawl.
- No cross-context imports. Cross-domain state goes via prop drilling at the page boundary or, when warranted, a thin `AppContext` composed at `src/main.tsx`.
- If a context starts shouldering large lists or selector-driven re-renders, raise the question in a dedicated turn before reaching for an external state lib.
## Routing

- Phase 1 / Phase 2 stub: **no router**. A single `<App />` renders the (eventual) chat shell.
- A router is introduced only when admin pages merge in (dev_plan task #36, Phase 5). Target shape at that point: `/` chat, `/history`, `/admin/*` admin (RBAC-gated by backend), `/health` debug.
- Admin pages will live under `src/pages/admin/`. They are part of the same SPA — no separate Streamlit, ever.
## Conventions

- TypeScript `strict: true`.
- No `any`. Use `unknown` + type narrowing.
- Plain CSS Modules (`*.module.css`) for component styling — no global CSS leaks. If a UI library is later adopted, prefer its idiomatic styling primitive (e.g. Fluent UI `makeStyles`) over CSS Modules for new components in that library's scope.
- **Tests live under `v2/src/frontend/tests/`, mirroring the `src/` tree** (e.g. `src/pages/chat/ChatPage.tsx` → `tests/pages/chat/ChatPage.test.tsx`). Every new component ships with a corresponding `tests/.../<Component>.test.tsx` covering at least one behavioral assertion. **Do not colocate `*.test.tsx` next to source files.** The Vitest `include` glob in `vite.config.ts` only scans `tests/**`, so colocated tests will be silently skipped.
## Branding / customization

- All branding text/logo loaded at runtime from `/api/admin/ui-config` (backed by `active.json`). *(That endpoint lands in Phase 5 — dev_plan task #35. Until then, the placeholder shell may use a single hard-coded title; replace it the moment the endpoint exists.)*
- Do not hardcode "Chat With Your Data" in components once the config endpoint exists — use the config.
