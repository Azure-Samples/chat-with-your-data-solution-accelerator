/**
 * Pillar: Stable Core
 * Phase: 7 (Testing + Documentation)
 *
 * Shared closed-set status discriminators for the admin + chat
 * pages. Each enum follows the `as const` + literal-union pattern
 * documented in [.github/instructions/v2-frontend.instructions.md]
 * (Enums section) and mirrors the backend's Python `StrEnum`
 * discipline (Hard Rule #11): consumers reference `Foo.Bar` at
 * call sites; the type narrows to the bare-string union so wire
 * payloads, reducer actions, and storage keys round-trip without
 * `as` casts. Domain-specific enums (StreamChannel, MessageRole)
 * stay in `models/chat.tsx`; cross-domain status enums live here.
 */

export const LoadStatus = {
  Loading: "loading",
  Loaded: "loaded",
  Failed: "failed",
} as const;
export type LoadStatus = (typeof LoadStatus)[keyof typeof LoadStatus];

export const SaveStatus = {
  Idle: "idle",
  Saving: "saving",
  Success: "success",
  Failed: "failed",
} as const;
export type SaveStatus = (typeof SaveStatus)[keyof typeof SaveStatus];

export const UploadStatus = {
  Pending: "pending",
  Uploading: "uploading",
  Success: "success",
  Failed: "failed",
} as const;
export type UploadStatus = (typeof UploadStatus)[keyof typeof UploadStatus];

export const SubmitStatus = {
  Pending: "pending",
  Submitting: "submitting",
  Success: "success",
  Failed: "failed",
} as const;
export type SubmitStatus = (typeof SubmitStatus)[keyof typeof SubmitStatus];

export const ReprocessStatus = {
  Idle: "idle",
  Confirming: "confirming",
  Running: "running",
  Success: "success",
  Failed: "failed",
} as const;
export type ReprocessStatus =
  (typeof ReprocessStatus)[keyof typeof ReprocessStatus];

export const RowDeleteStatus = {
  Idle: "idle",
  Deleting: "deleting",
  Failed: "failed",
} as const;
export type RowDeleteStatus =
  (typeof RowDeleteStatus)[keyof typeof RowDeleteStatus];
