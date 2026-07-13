# ADR 0011 — Frontend wire shapes + domain state types extracted into `src/models/<domain>.tsx`

- **Status**: Accepted
- **Date**: 2026-06-02
- **Phase**: Phase 7 close-out (FE conventions refactor U-P7-FE-REFAC-0)
- **Pillar**: Stable Core (frontend layout policy)
- **Deciders**: CWYD v2 maintainers
- **Supersedes**: nothing. This ADR introduces the FE-side counterpart of the BE convention that already pins request/response types in `v2/src/backend/models/<domain>.py`.

## Context

The v2 frontend grew organically from a Phase-1 scaffold. Wire shapes (the TypeScript interfaces that mirror backend Pydantic models — the JSON contract crossing `fetch()`) and domain state shapes (e.g. `ChatMessage`, `ChatState`, `HistoryConversation`) were declared inline next to their first consumer:

- `AdminStatus` in [`src/api/admin.ts`](../../src/frontend/src/api/admin.ts).
- `SpeechConfigPayload` in [`src/api/speech.ts`](../../src/frontend/src/api/speech.ts).
- `StreamMessage` + `StreamEvent` in [`src/api/streamChat.ts`](../../src/frontend/src/api/streamChat.ts).
- `ChatMessage` + `ChatState` in [`src/pages/chat/ChatContext.tsx`](../../src/frontend/src/pages/chat/ChatContext.tsx).
- `HistoryConversation` in [`src/pages/chat/components/HistoryPanel.tsx`](../../src/frontend/src/pages/chat/components/HistoryPanel.tsx).

This worked while the FE surface was small, but three problems surfaced as the surface grew:

1. **Wire-shape duplication risk.** When a second consumer needed `AdminStatus`, the natural reflex was to re-declare it locally or to import it from the API client file — both of which made `api/admin.ts` simultaneously a fetch wrapper *and* a type module, two responsibilities in one file.
2. **FE/BE drift surface is invisible.** A backend field rename in `v2/src/backend/models/admin.py` should immediately surface as a type error on the FE side. With shapes scattered across `api/*.ts`, `pages/chat/*.tsx`, and `pages/chat/components/*.tsx`, the failure is N type errors across N files — no single anchor point that says "this is the wire contract."
3. **Asymmetry with the backend.** BE pins wire shapes in `v2/src/backend/models/<domain>.py` (e.g. `admin.py`, `chat.py`). The FE had no symmetric concept, which made the question "where does the `AdminStatus` interface live?" a search problem instead of a structural one.

The Phase 7 #53 Ingest Data admin work was about to add three more wire shapes (`IngestUrlResponse`, `UploadResponse`, `ReprocessResponse`). Adding them to `api/admin.ts` would have doubled-down on the asymmetry. The decision point arrived at the moment a new feature would have entrenched the pattern further.

## Decision

**Wire shapes (request / response payloads from BE) and domain state types live in `v2/src/frontend/src/models/<domain>.tsx` — one file per backend domain module. Component prop interfaces, hook-shape interfaces, and reducer action-union types stay inline next to their consumer.**

The split rule:

| Type kind | Lives in | Example |
|---|---|---|
| Wire shape (mirrors a BE Pydantic model) | `src/models/<domain>.tsx` | `AdminStatus`, `IngestUrlResponse`, `UploadResponse`, `ReprocessResponse`, `SpeechConfigPayload`, `StreamMessage`, `StreamEvent` |
| Domain state (the shape the FE keeps in a context/reducer) | `src/models/<domain>.tsx` | `ChatMessage`, `ChatState`, `HistoryConversation` |
| Component prop interface | inline next to the component | `HeaderProps`, `ChatPageProps`, `FeedbackButtonsProps`, `HistoryPanelProps` |
| Hook-shape interface | inline next to the hook | `UseSpeechRecognition` |
| Reducer action-union types | inline next to the reducer | `ChatAction` union in `ChatContext.tsx` |
| Tooling / framework prop types | inline | `CoralShellRowProps`, `MsftColorLogoProps` |

The domain split mirrors the backend exactly:

| Frontend file | Mirrors backend module |
|---|---|
| `models/admin.tsx` | `v2/src/backend/models/admin.py` |
| `models/chat.tsx` | `v2/src/backend/models/conversation.py` + `v2/src/backend/models/history.py` (FE collapses both into one chat-domain file) |
| `models/speech.tsx` | `v2/src/backend/models/admin.py` Speech section + speech endpoint shapes |
| `models/feedback.tsx` | `v2/src/backend/models/feedback.py` (placeholder file; backend has no `feedback.py` today — file exists for symmetry as the surface grows) |

API client modules (`src/api/<domain>.tsx`) import types from `src/models/<domain>` via `import type { ... }`. They no longer declare wire shapes themselves.

## Consequences

### Positive

- **Single FE/BE drift anchor.** A backend wire-shape change produces a type error in one file (`models/<domain>.tsx`), not N files. The error is also at the location a reader expects to find it.
- **API client modules become pure transports.** `api/admin.tsx` is now exclusively `fetch()` wrappers — easier to read, easier to test, easier to mock.
- **Symmetric with the backend.** "Where does shape X live?" has the same answer on both sides: `models/<domain>`. New contributors only need to learn one rule.
- **Easier OpenAPI client migration later.** When v2 wires an OpenAPI generator (deferred per [v2-frontend.instructions.md](../../../.github/instructions/v2-frontend.instructions.md)), the generated types land in `src/api/generated/`. The hand-rolled `models/` directory becomes the FE-curated layer on top of generated types — a clean swap, not a reorganization.

### Negative

- **One-time refactor cost.** Every existing inline shape moves once. Bounded by the count of shapes (currently 7 wire/domain shapes; ~30 minutes of mechanical work).
- **Two-file edits for a new BE shape.** Adding a new endpoint touches `models/<domain>.tsx` *and* `api/<domain>.tsx`. Acceptable — the alternative (single-file declaration) is exactly what this ADR is removing.

### Neutral

- **Prop / hook / reducer-action types stay inline.** These are local contracts that change with the consumer, not wire shapes. Moving them would scatter unrelated changes across files. The split rule above is binding — do not migrate inline types into `models/`.
- **`models/<domain>.tsx` files use `.tsx` extension** per ADR 0013, even though they contain no JSX. This is a layout decision, not a styling one — the extension is uniform across `src/`.

## Alternatives considered

1. **Keep inline declarations; add a `// WIRE SHAPE` comment marker.** Rejected — relies on grep discipline, doesn't survive refactors, and doesn't solve the drift-anchor problem.
2. **Single `src/types.tsx` file holding all wire shapes.** Rejected — collapses domain boundaries that the backend explicitly enforces, and creates a god-file that everything imports from.
3. **`src/types/<domain>.tsx` instead of `src/models/<domain>.tsx`.** Rejected — "types" reads as "TypeScript-specific" (utility types, mapped types, generic helpers), which is a different concern. "Models" matches the backend directory name and reads as "the shape of data."
4. **`src/api/<domain>/types.tsx` co-located with the API client.** Rejected — couples wire-shape location to API client structure. A wire shape consumed by both an API client *and* a Context provider (`ChatMessage` is both an HTTP response field *and* state shape) would awkwardly live under `api/`.

## References

- [`.github/copilot-instructions.md`](../../../.github/copilot-instructions.md) Hard Rule #11 — TypeScript naming + extension conventions (amended by ADR 0013 to land `.tsx`-everywhere).
- [`.github/instructions/v2-frontend.instructions.md`](../../../.github/instructions/v2-frontend.instructions.md) — `## Models` section codifies the structural rule this ADR ratifies.
- [ADR 0012](0012-frontend-test-folder-mirror.md) — companion FE-layout ADR (tests live under `tests/` mirror tree).
- [ADR 0013](0013-frontend-strict-ts-and-tsx-everywhere.md) — companion FE-layout ADR (`.tsx` everywhere + extra strict TS flags).
- [`development_plan.md`](../development_plan.md) `U-P7-FE-REFAC` debt row — tracks the refactor turns that land this ADR.
