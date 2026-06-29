<!-- markdownlint-disable-file -->
# Release Changes: MACAE-parity end-to-end `azd up`

**Related Plan**: azd-up-e2e-deployment-plan.instructions.md
**Implementation Date**: 2026-06-29

## Summary

Close four MACAE-parity gaps so a default `azd up` plus the post-deploy seed yields an immediately-usable CWYD v2: backend CORS + admin-open flag, frontend Easy Auth declaratively disabled, and an unattended seed that verifies the index is populated. Validated live on Azure.

## Changes

### Added

* (pending)

### Modified

* v2/infra/main.bicep - Phase 1: added two entries to the backend `backendContainerApp` `containers[0].env` first array. `BACKEND_CORS_ORIGINS` = `'https://app-frontend-${solutionSuffix}.azurewebsites.net'` (cycle-free, suffix-derived) at the end of the array; `AZURE_AI_SEARCH_INDEX` = `'cwyd-index'` after `AZURE_AI_SEARCH_ENDPOINT` (defensive pin). Bicep compiles clean (EXIT=0). Phase 2: added `AZURE_REQUIRE_ADMIN_AUTH` = `'false'` to the same env array and rewrote the `AZURE_ENVIRONMENT` comment (production now governs runtime-mode + chat `get_user_id` bypass only; admin wall governed by the new flag). Phase 3: on the `frontendWebApp` AVM `web/site:0.22.0` module, added a `configs` param with one `authsettingsV2` entry that declaratively DISABLES Easy Auth (`globalValidation.requireAuthentication=false`, `unauthenticatedClientAction='AllowAnonymous'`, `platform.enabled=false`) — schema-valid against 0.22.0 `authSettingsV2ConfigType`, no env-specific identity provider/clientId/issuer; and added `WEBSITES_PORT='8000'` + `ENABLE_ORYX_BUILD='true'` to the `siteConfig.appSettings` first array (alongside the existing `SCM_DO_BUILD_DURING_DEPLOYMENT`, not duplicated). Bicep compiles clean (EXIT=0; only pre-existing BCP081/BCP334 warnings).
* v2/src/backend/core/settings.py - Phase 2: added `require_admin_auth: bool = False` to `AppSettings` (resolves `AZURE_REQUIRE_ADMIN_AUTH`); rewrote the `environment` field comment for accuracy.
* v2/src/backend/dependencies.py - Phase 2: in `requires_role._checker`, hoisted `allow_open_admin = environment is LOCAL or not require_admin_auth` and relaxed BOTH fail-closed 401 branches to return the synthetic user when open; malformed-claims 401 and role 403 untouched.
* v2/tests/backend/core/test_settings.py - Phase 2: +2 tests (default False, env override True).
* v2/tests/backend/test_dependencies.py - Phase 2: extended `_settings()` helper + 4 tests (open-admin returns user in prod, wall-on 401, valid role returns principal, role 403 still enforced).
* v2/scripts/upload_sample_data.py - Phase 4: Step 4.1 changed `resolve_selection` non-TTY fallback from `SeedScope.SKIP` to `AssistantType.DEFAULT` (PDF happy-path corpus) and reworded the notice (`AZURE_ENV_SAMPLE_DATA=none` is the explicit opt-out; `none` token still maps to SKIP above the branch). Step 4.2 added the pure injectable `wait_for_index_completion(count_fn, expected_min, timeout_s, interval_s, sleep_fn, monotonic_fn, output_fn) -> bool` helper (loud PASS / FAIL+remediation banner; injected clock/sleep, no real waits) and wired it into `main()` after enqueue: builds a `SearchClient` (reused credential) only when both `AZURE_AI_SEARCH_ENDPOINT`+`AZURE_AI_SEARCH_INDEX` are set, captures a pre-upload `baseline`, polls for `baseline + uploaded`; the `_index_document_count` closure wraps `get_document_count()` in `except (AzureError, HttpResponseError)` with a stderr warning + last-known hold (Hard Rule #14, bounded timeout owns the verdict); closes the search client in `finally`; FAIL banner does NOT change exit code (postdeploy stays `continueOnError: true`, PD-03). Skips the check with a notice when the search env vars are absent.
* v2/tests/scripts/test_upload_sample_data.py - Phase 4: renamed `test_resolve_selection_non_tty_skips` → `test_resolve_selection_non_tty_defaults`; added `test_resolve_selection_non_tty_none_token_opts_out` and two `wait_for_index_completion` tests (PASS on count-reaches-min; FAIL+remediation on fake-clock timeout). 22 passed.
* v2/tests/backend/test_admin.py - Phase 5 (Phase 2 regression fix): added a `require_admin_auth: bool = True` param to the shared `_settings()` stub and wired it into the returned `NS(...)`. The 10 admin auth-gate tests exercise the real `requires_role` checker (the rest override `REQUIRE_ADMIN_USER`), which now reads `settings.require_admin_auth`; the stub lacked the field after the Phase 2 dependencies change, raising `AttributeError`. Default True keeps the production-wall tests meaningful; production code default stays False (admin open by default).

### Removed

* (pending)

## Additional or Deviating Changes

* Step 1.3 (cosmetic admin-display env cluster) intentionally SKIPPED — optional per plan; deferred to keep the diff surgical and avoid env-var churn. No functional impact. Tracked as DR-03 in the planning log.
* Step 4.3 (reused-resource self-heal in `post_provision.py`) intentionally SKIPPED — PD-02 default is a FRESH-resource deploy, so the reconcile branch is not needed. `post_provision.py` untouched. Tracked as DR-04 / PD-02 in the planning log.
* Phase 4 follow-on flagged (not back-filled inline per Hard Rule #12): a `main()`-level test exercising the wired search poll with a fake `SearchClient` would close the gap between the helper unit tests and the `main()` wiring — deferred to the end-of-phase audit. Recorded as WI in the planning log.
* Phase 2 regression caught at the Phase 5 local gate: 10 `test_admin.py` auth-gate tests failed with `AttributeError: ... 'require_admin_auth'` because the shared `_settings()` stub was not updated when Phase 2 added the `require_admin_auth` read to `dependencies.requires_role`. The Phase 2 unit ran only the settings + dependencies test files, not the admin router suite. Fixed by adding the field to the stub (default True). Tracked as DD-04 in the planning log.

## Release Summary

(pending final phase)
