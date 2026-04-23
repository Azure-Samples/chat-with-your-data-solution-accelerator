---
description: "CWYD v2 React/Vite frontend conventions. Use when: editing v2/src/frontend/**, adding a page, adding a component, wiring the API client, consuming the SSE reasoning stream, adding a Zustand store, adding a plugin slot, branding the UI, or merging admin pages."
applyTo: "v2/src/frontend/**"
---

# v2 Frontend (React + Vite) Conventions

## Stack

- React 19, TypeScript 5.9+, Vite 7+, Fluent UI v9 (prefer over v8 for new components), Zustand for state, React Router 7.
- Testing: Vitest + Testing Library + MSW for API mocking. (Jest remains for files migrated from v1, but new tests use Vitest.)

## Plug-and-play surface

- All API calls go through `src/api/client.ts` which reads `import.meta.env.VITE_BACKEND_URL`.
- The OpenAPI client is **generated** into `src/api/generated/`. Do not hand-edit. Regenerate via `make openapi` or the pre-commit hook.
- Plugin slots: a `<PluginHost slot="chat-toolbar" />` component renders any registered plugin for that slot. Custom integrators add plugins via `registerPlugin({slot, component})`. Slots so far: `chat-toolbar`, `message-actions`, `admin-nav`, `reasoning-renderer`.

## SSE consumption (reasoning channel)

- `src/api/sse.ts` exposes `useEventStream(url, body)` that yields typed `OrchestratorEvent` objects.
- The chat page renders:
  - `answer` events → message body.
  - `reasoning` events → collapsible "Show reasoning" panel (default collapsed).
  - `tool` events → step indicators.
  - `citation` events → footnote list.
  - `error` events → error toast, close stream.

## Stores (Zustand)

- One store per domain: `useChatStore`, `useHistoryStore`, `useAdminStore`, `useSettingsStore`.
- No cross-store imports. Cross-domain state goes via React Query or props.

## Routing

- `/` chat, `/history`, `/admin/*` admin (RBAC-gated by backend), `/health` debug.
- Admin pages live under `src/pages/admin/`. They are part of the same SPA — no separate Streamlit, ever.

## Conventions

- TypeScript `strict: true`.
- No `any`. Use `unknown` + type narrowing.
- CSS Modules or Fluent UI `makeStyles` — no global CSS leaks.
- Every new component has a `<Component>.test.tsx` covering one behavioral assertion minimum.

## Branding / customization

- All branding text/logo loaded at runtime from `/api/admin/ui-config` (backed by `active.json`).
- Do not hardcode "Chat With Your Data" in components — use the config.
