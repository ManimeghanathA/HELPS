# HELPS Workflow Revision Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Complete scoped red/green verification, integration and independent review before delivery.

**Goal:** Deliver the approved simpler HELPS recommendation and chronological temporal-build workflows with a professional dark/light interface.

**Architecture:** Preserve normalized immutable knowledge packages and all existing measured features. Separate hard-check outcomes, research candidate ranking and verification evidence; replace technical engineering inputs with named sources, date selection and versioned jobs. Preserve original history read-only and compute dated overlap on current geometries.

**Tech Stack:** Existing Flask/Python, GeoPackage/GeoPandas/Rasterio/Shapely, Leaflet and plain JavaScript.

**Spec:** `docs/superpowers/specs/2026-10-14-helps-workflow-revision-design.md`, approved 2026-10-14. User subsequently added hard-only elimination, full scoring audit and dark mode, and explicitly instructed implementation without further delay.

## Constraints and execution ruling

- Use the existing isolated draft clone; no merge, remote publication, source deletion or current-package replacement.
- Hard failures alone reject terrain candidates; unknown hard/environment evidence remains explicitly unverified, never passed. Essential absent/invalid geometry cannot be presented as a mapped recommendation.
- Preserve all eleven balanced soft factors, other mission priorities and every polygon feature/provenance field. Low/missing soft factors do not eliminate. Research rank and verified clearance remain separate.
- New observation dates must exceed the active region date (Bhadra baseline 2026-06-01); creation timestamps do not count. Recheck publication/activation; historical import/browsing remains allowed.
- Original five historical observations and June current reference are evidence; validate hashes/grids/state encoding and recompute geometric overlaps. Never ID/row-join old aggregate scores to new polygons.
- User explicitly authorized parallel execution earlier and now instructed building without further delay. Preserve that execution method; this concrete plan proceeds under that authorization rather than another permission gate.

## Review focus

1. Unsupported weather at a different location must not earn a favourable soft factor; test source coverage and unknowns.
2. A nearly-full floating support fraction may pass only the declared roundoff tolerance; genuine gaps stay unknown.
3. History raster state encoding/provenance may differ; validate/reject incompatible artifacts and distinguish cloud from non-open.
4. Equal/older/future observation dates and an activation race must not overwrite the current version.
5. Map pick mode, delayed region responses, theme persistence and slope interval endpoints must retain correct selection and evidence.

## A: Hard checks and research ranking

**Owner:** Recommendation agent. Files: `scripts/recommendation/**`, `helicopter_profiles.py`, focused Python tests. No UI/API edits.

**Contracts:** Extend recommendation response with `research_candidates`, `research_count`, `distinct_opportunity_counts`, `verification_state`, readable missing-verification reasons and factor weight coverage; preserve existing eligible/uncertain/excluded contracts. Export three supported UI profiles with LCH/LUH/ALH short names and primary-source dimension provenance.

- [ ] Write tests showing a failed hard check cannot rank, low/missing soft values do not reject, unknown environment can rank only as unverified research, and absent geometry is not mapped.
- [ ] Observe failing focused tests, then implement explicit hard-check policy and research ranking without rewriting gate unknowns as pass.
- [ ] Audit scales/units and formula `100 * sum(w*f)/sum(supported w)`, finite bounds, factor coverage, monotonicity, missing weather coverage, full weight inventory and deterministic spatial deduplication; add numeric expected-contribution tests.
- [ ] Verify aircraft dimensions using HAL primary sources; separate verified dimensions from configured unverified operational limits. Test exact effective profile serialization.
- [ ] Run all recommendation tests and report changes, evidence and limitations for independent review.

## B: Temporal knowledge, monthly discovery and engineering API

**Owner:** Pipeline agent. Files: `scripts/knowledge/**`, `scripts/pipeline/monthly*.py`, `scripts/ui/api.py`, `scripts/ui/jobs.py`, focused Python tests. No frontend or recommendation edits.

**UI contracts:** `GET /api/knowledge/workflow?region_id=bhadra` returns `region_id,current_dataset_id,current_date,minimum_new_date,history,sources` (named source selectors, internal IDs assigned server-side). `POST /api/knowledge/imagery-search` accepts `region_id,end_date`; returns `search_id,status`. `GET /api/knowledge/imagery-search/<search_id>` returns bounded status/months/observations, actual metadata-versus-measured QA and errors. `POST /api/knowledge/build` accepts `region_id,date,source_mode,source_choices` with named registered/reviewed sources; returns existing `job_id,status`. Existing job/publish/activate endpoints remain usable. Source choices can refer to reviewed catalog names or managed uploads; never arbitrary paths.

- [ ] Write chronology and current-preservation tests, observe red, implement shared backend date validation at build/publication/activation and readable workflow metadata. Preserve explicitly administrative historical recovery helpers separate from ordinary forward-only API.
- [ ] Write synthetic raster tests for exact polygon overlap, holes, missing support, no valid confidence, incompatible classes/CRS and date uniqueness. Implement normalized dated temporal observations and aggregates for both stored geometry entities, plus repository access/export. Keep backwards-compatible old packages.
- [ ] Discover original dated artifacts read-only with source manifests/hashes and declared encoding; expose dates, include prior current date as history for newer observations, reject relabelled old spectral/SCL data.
- [ ] Write monthly search fixtures for twelve buckets, missing months, same-day mosaics and provider errors; implement bounded catalog shortlist and measured SCL quality where available, explicitly distinguish metadata-only candidates. Preserve product IDs/actual timestamps, cache and progress. Never claim an unperformed acquisition succeeded.
- [ ] Adapt named-source build request to existing bounded acquisition and complete knowledge builder. Actual source dates must match the new date. Record temporal counts/support in validation summaries and version timeline.
- [ ] Run focused source/build/repository/API tests and a real small-area historical integration; preserve current Bhadra dataset.

## C: Professional application and engineering UX

**Owner:** UI agent. Files: `templates/workspace.html`, `static/workspace*.js/css`, `static/map_view.js`, new focused frontend helpers/tests. No Python/API edits.

**Consumes:** A's response/profile extensions; B's workflow/search/build API. Gracefully display absent fields/provider errors during integration, never fabricate fixtures as real evidence.

- [ ] Write behavioral tests for three-model selection/effective aircraft card, typed/click/drag coordinate synchronization, explicit position-pick mode and recommendation selection retaining full holes/parts/query position.
- [ ] Implement readable research recommendation cards with score, hard outcomes, missing verification, reasons and supported/missing scoring factors. Remove raw JSON/policy controls and parent/child wording from the ordinary UI.
- [ ] Write interval endpoint/unknown tests, implement mutually exclusive native measured slope bands rather than mean-colouring whole polygons or cumulative overlays; retain numeric degree legend and exclusions.
- [ ] Replace engineering form with six-step region/search/date/sources/build/review flow; show actual current/history dates, minimum new date, named reusable/uploaded sources, search QA status and failed job recovery. No asset-ID/JSON input requirement.
- [ ] Implement coherent dark default and light theme, persisted preference, readable typography, spacing, responsive layout, keyboard focus and accessible contrasts for maps/tables/forms. Use CSS/DOM, no generated mock artwork.
- [ ] Run all Node behavioral tests; report DOM/screenshot requirements for controller browser verification.

## D: Integration, evidence and local delivery

**Owner:** Controller. Files: small integration fixes, documentation and acceptance evidence; coordinate owner edits to avoid collisions.

- [ ] Verify producer/consumer keys and all feature inventories, run complete Python and Node suites once integrated; fix meaningful regressions and repeat affected checks only.
- [ ] Independently review hard/soft policy, score arithmetic, chronology, temporal area accounting and exclusive bands. Resolve findings with focused regression verification.
- [ ] Use real Bhadra browser walkthrough: both themes/roles, model cards, map selection, populated ranking with explicit verification badges, source search/error flow, later/equal/older date handling, slope shading and mobile layout. Record screenshots.
- [ ] Preserve original and current packages, save local reviewed commits and update acceptance documentation with measured results and any external-provider limits; no remote push/merge.
