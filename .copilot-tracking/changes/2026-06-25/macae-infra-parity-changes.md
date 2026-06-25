<!-- markdownlint-disable-file -->
# Release Changes: MACAE infra parity — one-shot `azd up` for CWYD v2

**Related Plan**: macae-infra-parity-plan.instructions.md
**Implementation Date**: 2026-06-25

## Summary

Make CWYD v2 deploy end-to-end with a single `azd up` by adopting MACAE's patterns: frontend on App Service build-from-source, backend image by name+tag, post-deploy sample-data upload, and durable back-port of the A1–A11 manual-change debt. Implemented unit-by-unit (test-first) per the CWYD one-unit-per-turn contract.

## Changes

### Added

* v2/scripts/package-frontend.sh / .ps1 - Step 1.3: prepackage wrappers (npm ci && npm run build, then stage the deploy artifact); no VITE_BACKEND_URL bake (runtime /config).
* v2/scripts/package_frontend.py - Step 1.6: assembles the App Service deploy artifact (server + requirements.txt + static dist/) at src/frontend/build-output.
* v2/tests/scripts/test_package_frontend.py - Step 1.3/1.6: wrapper textual contract + build_artifact assembly tests.
* v2/src/frontend/src/api/runtimeConfig.tsx - Step 1.5b: shared runtime-config seam that fetches /config once at boot (Phase Implementor) + its vitest test.

### Modified

* v2/src/frontend/frontend_app.py - Step 1.1: `_DIST_DIR` default now resolves relative to the module file (`Path(__file__).parent / "dist"`) so it works on App Service (wwwroot) and in the Docker prod stage (`/usr/src/app/dist`) unchanged. Step 1.5a: added a `GET /config` route (before the catch-all) returning the `BACKEND_API_URL` env value.
* v2/tests/frontend_app/test_frontend_app.py - Step 1.1/1.5a: module-relative-default test + /config route test.
* v2/azure.yaml - Step 1.2/1.6: frontend service now `host: appservice` + `dist: ./build-output` + service-scoped `prepackage` hook (no `docker:` block); fixes BUG-0081.
* v2/infra/main.bicep - Step 1.4: frontend App Service `linuxFxVersion` → `PYTHON|3.11` + uvicorn `appCommandLine`; appSettings swap `VITE_BACKEND_URL` → `BACKEND_API_URL` (runtime /config). (Phase Implementor; `az bicep build` clean.)
* v2/src/frontend/src/App.tsx + src/api/{admin,conversationHistory,streamChat,speech}.tsx - Step 1.5c–1.5g: converged the 5 build-time `VITE_BACKEND_URL` reads onto the runtime-config seam (Phase Implementor) + tests.
* v2/.gitignore - Step 1.6: ignore `src/frontend/build-output/` (the assembled deploy artifact).
* v2/infra/main.bicep - Phase 2: A10 `azureADAuthenticationAsArmPolicyStatus: 'enabled'` on the ACR module; A11 `registries:` block on `backendContainerApp` (UAMI pull); backend image params (`backendContainerRegistryHostname`/`ImageName`/`ImageTag`) + first-provision-safe conditional image (`empty(hostname) ? MCR placeholder : '${hostname}/${name}:${tag}'`, DD-03). `az bicep build` clean.
* v2/azure.yaml - Phase 2 (Step 2.3a): `docker.remoteBuild: true` on `services.backend`.
* v2/infra/main.parameters.json - Phase 2 (Step 2.3c): `backendContainerRegistryHostname` = `${AZURE_CONTAINER_REGISTRY_ENDPOINT=}`, `backendContainerImageTag` = `${AZURE_ENV_IMAGE_TAG=latest}`.

### Removed

* (none yet)

## Additional or Deviating Changes

* Phase 4 (KB MCP project connection) is DEFERRED — blocked on WI-01 (the `cwyd-kb-mcp` RemoteTool connection schema is unconfirmed; planning log DR-01).
* Phases 2–6 (and Step 1.4) edit `v2/infra/main.bicep`; the operator previously paused bicep edits (planning log PD-05). Confirmation requested before the infra back-port proceeds — see the turn's Implementation Decisions.
* Execution is unit-by-unit (one method/class + its test per turn) per CWYD Hard Rule #1, rather than whole-phase batches.
* Step 1.6 (deploy-artifact assembly) was ADDED during implementation: `dist: ./dist` would upload only the built SPA, but the App Service start command `uvicorn frontend_app:app` needs the server + requirements.txt at the deploy root. Resolved by staging a self-contained artifact at `src/frontend/build-output` (server + requirements.txt + static dist/) and pointing `services.frontend.dist` at it — the MACAE-aligned pattern. `project` stays `./src/frontend` (a real dir) so the azd schema linter is satisfied.
* ID-02 (PD-01) = runtime `/config` (MACAE-exact): the frontend build does NOT bake `VITE_BACKEND_URL`; the SPA fetches the backend URL once at boot from `/config` fed by the `BACKEND_API_URL` app setting. Reverses the planning-log DD-01 default.
* A10 schema correction: the AVM `container-registry/registry:0.12.1` module exposes a FLAT scalar param `azureADAuthenticationAsArmPolicyStatus: 'enabled'`, not the nested `policies: { azureADAuthenticationAsArmPolicy: { status } }` the plan/research assumed (BCP037 on the nested shape). Applied the verified flat param.

## Release Summary

(pending — added after the final phase)
