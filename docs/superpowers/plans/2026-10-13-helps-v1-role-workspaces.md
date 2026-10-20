# HELPS V1 Role Workspaces Implementation Plan

Delivery status: implemented and verified locally; see `docs/v1-acceptance.md` for acceptance evidence and remaining external-input limits. The task instructions below are retained for reproducibility.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the Data Engineer pipeline/knowledge UI and Application User India→region→recommendation/table/map workflow with real slope shading.

**Architecture:** A role-aware Flask shell uses shared selected-region/dataset/map/detail state. Engineering builds and publication are separate from read-only published-data exploration; both roles share recommendation views and backend contracts.

**Tech Stack:** Flask, Leaflet, plain JavaScript/CSS, existing offline/recommendation modules.

**Spec:** `docs/superpowers/specs/2026-10-13-helps-v1-all-phases-design.md`; interfaces from the terrain-knowledge and recommendation plans.

## Global Constraints

- Two entry roles; Data Engineer has pipeline and recommendation workspaces; Application User has published-data exploration/recommendations only.
- Preserve the broader parent candidate map; slope child layers complement it.
- Three region views: Recommendations, View Candidates and View Map.
- Full holes/MultiPolygons, numeric slope degrees, `[0,2,4,6,8,10,12,15]` legend and distinct no-data styling.
- Actual selected dataset/region/date and source quality are visible; no fabricated counts, slope or surface defaults.
- Local loopback default; role selection is not a claim of authenticated identity.
- Clean startup must not depend on `.review-deps` or review-only launch scripts.

## Review Focus

- A role/view switch during a pending request cannot display another region's result.
- Candidate row, map click and recommendation selection resolve to the same entity/version.
- Missing slope must look different from zero slope, including on narrow screens.
- Failed upload/build/activation preserves previous published knowledge and useful error/progress state.
- Dense maps/tables remain responsive without simplifying authoritative geometry.

## Files and Contracts

Create `templates/workspace.html`, `static/workspace.js`, `static/workspace_state.js`, `static/map_view.js`, `static/workspace.css`, `scripts/ui/jobs.py` and `scripts/ui/api.py`; modify `app.py`. Preserve existing UI as a documented legacy/reference view during migration.

Published API: `GET /api/datasets`, `GET /api/datasets/<id>/terrain`, `GET /api/datasets/<id>/terrain/<terrain_id>`, `GET /api/datasets/<id>/zones?threshold=...`, `GET /api/datasets/<id>/slope`, and `POST /api/recommendations`.

Engineering API: `POST /api/knowledge/sources` for validated managed-source registration or streamed multipart upload, `POST /api/knowledge/jobs`, `GET /api/knowledge/jobs/<id>`, published artifact downloads, and explicit `POST /api/datasets/<id>/activate`. Source kinds are `aoi`, `dem`, `spectral`, `scl`, `osm`, `buildings`, `landcover`, `restriction`, `candidate_seed`; return an asset ID and source-validation report. Job payloads use registered asset IDs resolved into `KnowledgeBuildSpec`; arbitrary client filesystem paths are not accepted. All file access resolves inside managed input/published directories.

`createWorkspaceState()` in `workspace_state.js` exposes `selectRegion(region_id, dataset_id)`, `beginRequest() -> token`, `applyResponse(token, payload) -> bool`, and the current state snapshot. Region/dataset changes invalidate outstanding request tokens. Keep pure state helpers accessible to Node tests without requiring a bundler.

### Task 1: Role Entry, India Overview and Region Workspace

**Files:** Create workspace template/controller/styles; modify index routing in `app.py`; test `tests/test_role_routes.py`, `tests/test_workspace_state.cjs`.

- [ ] Write failing tests for both role paths, engineer-only navigation/actions, considered versus available regions, Bhadra selection and preserved selected version. Test out-of-order request responses after region changes.

```javascript
test('late response cannot replace another selected dataset', () => {
  const state = createWorkspaceState();
  state.selectRegion('bhadra', 'dataset-a');
  const oldToken = state.beginRequest();
  state.selectRegion('bhadra', 'dataset-b');
  assert.equal(state.applyResponse(oldToken, {spots: []}), false);
});
```
- [ ] Run focused Python and Node tests; observe failures.
- [ ] Implement role entry→India overview/dropdown→dedicated region workspace. Use explicit state IDs for role, region, dataset, selected terrain/zone, inputs and current request. Planned regions have no false availability/counts.
- [ ] Rerun tests; verify back-to-region/role navigation and loading/error/empty states.
- [ ] Review and commit.

### Task 2: Shared Geometry and Measured Slope Map

**Files:** Create `map_view.js`; extend workspace controller/styles; test `tests/test_slope_map.cjs`, `tests/test_dataset_api.py`.

**Interfaces:** `createMapView(container, callbacks)` exposes `showTerrain`, `showZones`, `focusTerrain`, `focusZone`, `showQueryPosition`, `showFootprint` and `setSlopeLayer`.

- [ ] Write failing tests for full rings/parts, centre/aircraft marker identity, degree legend boundaries, numeric slope details, absent-versus-zero slope and child overlays leaving parents available.
- [ ] Run tests and observe failures.
- [ ] Use `L.geoJSON` and canvas rendering where appropriate; serve selected-version slope evidence as a bounded raster/overlay plus child vectors. Show min/mean/max/support for parents and threshold/statistics for children. No-data gets a separate pattern/color.
- [ ] Rerun tests; inspect desktop/narrow-screen legend and feature panel, including a holey polygon.
- [ ] Review and commit.

### Task 3: Candidate Table and Linked Feature Details

**Files:** Extend workspace controller/template; dataset API in `scripts/ui/api.py`; test `tests/test_candidate_table.cjs`, `tests/test_dataset_api.py`.

- [ ] Write failing tests for stable pagination/filter/sort, unknown features, row→map→panel selection and selection persistence across views. Enforce a bounded page size.
- [ ] Run tests and observe failures.
- [ ] Render parent IDs, geometry, real terrain/context metrics and child availability from repository records. Selecting a row focuses its full polygon and the shared detail panel; direct map clicks select the same record.
- [ ] Rerun tests; measure table/map load on all 2,477 parents without a duplicate embedded copy of every dataset.
- [ ] Review and commit.

### Task 4: Recommendation Inputs, Top-K and Reasons

**Files:** Extend workspace controller/template; connect recommendation API; test `tests/test_recommendation_workspace.cjs`, `tests/test_recommendation_api.py`.

- [ ] Write failing tests for validated inputs, top-K ordering, request identity, selection focusing actual child boundary plus query coordinates, reason-panel factors/gates and empty/unknown explanations.
- [ ] Run tests and observe failures.
- [ ] Add aircraft/custom-feature, mission, coordinate, time/weather, radius and top-K controls. Render engine reasons/source dates, not canned safety claims. Preserve inputs while moving between recommendations/table/map.
- [ ] Rerun tests with controlled result fixtures; then exercise the populated Bhadra repository and backend together.
- [ ] Review and commit.

### Task 5: Data Engineer Source Form, Jobs and Publication

**Files:** Create `scripts/ui/jobs.py`, `scripts/ui/api.py`; extend engineering views; test `tests/test_engineering_jobs.py`, `tests/test_engineering_workspace.cjs`.

- [ ] Write failing tests for AOI/region/date and DEM/Sentinel/SCL/OSM/building/restriction inputs, import versus acquisition, invalid files/units/layers, managed-path containment, concurrent jobs, progress/failure history and activation that preserves prior knowledge.
- [ ] Run tests and observe failures.
- [ ] Implement managed source registration/streamed uploads and source validation preview. Run `build_knowledge` in a bounded worker, show real stage logs/results, and expose explicit validation/publication/activation. Include recommendation access for engineers. No real data is replaced by synthetic fixtures.
- [ ] Rerun tests; inspect a retained-seed Bhadra build and a failed-source run. Application User navigation has no build/publication controls; mutation endpoints validate their selected-role and local-origin policy.
- [ ] Review and commit.

### Task 6: Reproducible Launch, Export and Full-V1 Acceptance

**Files:** Update `README.md`, requirements/core-processing dependency files and supported launcher; add `docs/v1-acceptance.md`; tests `tests/test_v1_workflow.py`.

- [ ] Write failing end-to-end tests for selected package startup, both roles, all three user views, export version/geometry, a complete controlled recommendation chain and failed/unknown gates.
- [ ] Run tests and observe failures.
- [ ] Provide one supported launch command, installation/data requirements, build/example specifications, source attribution/license handling, exports and recovery instructions. Integrate existing acquisition dependencies without requiring review-only modules.
- [ ] Run all Python/Node tests, real Bhadra build/integrity checks and browser QA. Record preprocessing/query/map timings, screenshots, source gaps and acceptance evidence for each original phase.
- [ ] Review and commit; declare V1 complete only when its required deliverables are implemented and verified. Do not merge/push or publish remotely as part of this local plan without user authorization.

## Exact Task Verification Commands

Each command is run before implementation for meaningful failures and after implementation expecting exit 0:

| Task | Commands |
|---|---|
| 1 | `python -m pytest tests/test_role_routes.py -q`; `node --test tests/test_workspace_state.cjs` |
| 2 | `python -m pytest tests/test_dataset_api.py -q`; `node --test tests/test_slope_map.cjs` |
| 3 | `python -m pytest tests/test_dataset_api.py -q`; `node --test tests/test_candidate_table.cjs` |
| 4 | `python -m pytest tests/test_recommendation_api.py -q`; `node --test tests/test_recommendation_workspace.cjs` |
| 5 | `python -m pytest tests/test_engineering_jobs.py -q`; `node --test tests/test_engineering_workspace.cjs` |
| 6 | `python -m pytest tests -q`; `node --test tests/*.cjs` |
