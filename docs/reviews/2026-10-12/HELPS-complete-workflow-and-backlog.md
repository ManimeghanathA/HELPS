# HELPS complete workflow, progress, and pending work

Prepared 12 October 2026 from the full System Design Document, design-context notes, implementation plans, active source, retained outputs, and the Neha_branch review. This is a project inventory, not a new implementation plan or a claim that every historical design choice is still accepted. No application code was changed.

## Original purpose and architecture

The project was designed to transform terrain into reusable knowledge, then evaluate that knowledge for a selected helicopter and mission. The pilot retains the final decision. It was not designed around predefined helipads, isolated points, or repeatedly processing satellite imagery during every query.

**Offline knowledge generation:** AOI → satellite/DEM/GIS/restriction acquisition → standardization → candidate terrain → characterization → slope-based operational zones → environmental context → terrain knowledge database.

**Online recommendation:** position + aircraft profile + mission → nearby zones → weather feasibility → mandatory compatibility → footprint containment → mission ranking → explained top-K results.

An earlier text draft assigned Phase 7 to testing and Phase 8 to the interface. The full SDD assigns Phase 7 to UI/integration and Phase 8 to optimization/enhancement. Testing remains required across all phases. The eight phases below use the full SDD's names.

## Phase 1 — Geospatial data infrastructure

**Planned:** AOI selection; satellite, DEM, GIS and restricted-area acquisition; CRS/resolution/extent alignment; quality checks; versioned standardized data package.

**Finished implementation and retained work:** Bhadra AOI construction and boundary investigation; Polygon/MultiPolygon AOI validation; Sentinel-2 six-band/SCL preparation; tiled Copernicus acquisition, mosaicking and AOI clipping; OSM acquisition; Overture buildings; checksum manifests and partial-download recovery; Bhadra SRTM UTM raster and retained raw DEM sources; directory cleanup and archives; historical-date catalogue search and five published historical runs.

**Remaining:** AOI-wide DEM acquisition/preparation inside the generic runner; elevation units, vertical datum, nodata, resolution and alignment validation; authoritative restriction inputs and active integration; complete OSM water/industrial source package; source timestamps and scene/product provenance; reproducible dependencies; acquisition completeness and freshness policies for each source.

**Status:** Core Sentinel/vector infrastructure works. The complete planned package is partial because DEM and restrictions are not integrated into the active runner.

## Phase 2 — Candidate terrain generation

**Planned:** meaningful land-cover classification; permanent obstacle and restriction removal; contiguous terrain objects with complete geometry and stable IDs.

**Finished:** NDVI/MNDWI plus SCL screening; NOT_OPEN/POSSIBLE_OPEN/UNKNOWN encoding; cloud/shadow dilation; explicit water rejection in the current land-only detector; 8-connected polygonization; merged OSM/Overture building subtraction; polygon fragmentation; Neha's per-class NDVI calibration and water/industrial exclusions; saved intermediate and final artifacts.

**Remaining:** labelled detection evaluation; fuller surface/land-cover classification; towers, poles, power lines, tree margins, cliffs and other obstacles beyond building footprints; restricted-area integration; independent water/industrial audits; fail-closed required-layer reads; classification calibration supported by held-out evidence; stable parent terrain identities across stages/runs.

**Status:** A functional candidate-land implementation exists. “All permanent-obstacle-free terrain” is not established.

## Phase 3 — Terrain characterization

**Planned:** each terrain object's geometry, surface composition/coverage, vegetation density, water presence, terrain properties and accessibility. Features describe terrain independently of aircraft.

**Finished:** polygon area, minimum-rotated-rectangle length/width, clearance measurements on refined polygons; current-date candidate database and historical evidence aggregation implemented locally.

**Remaining:** surface class proportions; vegetation coverage; water-presence/proximity descriptors; road distance/connectivity; settlement/rescue context; elevation, slope distribution and roughness; explicit evidence limits for firmness, marsh, sand and loose soil; versioned temporal evidence; unknown/confidence fields. Geometric rectangle dimensions must not be described as guaranteed clear dimensions.

**Status:** Geometry exists; most descriptive terrain knowledge is absent. The temporal implementation has a confirmed negative-class bug and is not trustworthy yet.

## Phase 4 — Operational zone generation

**Planned:** compute cell-level DEM slope; segment multiple slope thresholds; intersect with obstacle-cleaned terrain; extract connected regions; characterize each region; compute pole of inaccessibility and maximum inscribed circle; store parent terrain and slope threshold; attach environmental context.

The SDD lists example thresholds ≤0°, 2°, 4°, 6°, 8°, 10°, 12°, 15°. These are documented design values, not validated operational limits. Threshold policy and DEM uncertainty still require evaluation.

**Finished:** 900 m²/30 m geometry gates; 15 m inward erosion, reconstruction and clipping; disconnected-child extraction; repeated child gates; polylabel at 0.5 m tolerance; clearance radius/diameter and representative coordinates; saved centre layer; topology and raster-state checks.

**Critical distinction:** the existing `operational_zone_extraction.py` removes narrow necks using geometry. It does not compute DEM slope or produce the planned slope-threshold zones. The shared name hides an unfinished major module.

**Remaining:** actual slope/roughness raster; nodata and uncertainty handling; multi-threshold connected zones; parent-child lineage; nested-threshold relationships/deduplication; per-zone recomputation of geometry/MIC; surface and obstacle intersection; footprint-scale terrain evaluation appropriate to available DEM detail.

**Environmental work remaining:** road access; water proximity; surrounding trees/buildings/towers/power features; obstacle density and height/coverage uncertainty; terrain-openness/approximate approach score. No flight-path certification is implied by the planned contextual score.

**Status:** Clearance geometry is implemented. The planned slope-based generation and environmental module are largely pending.

## Phase 5 — Terrain knowledge database

**Planned:** AOI → terrain object → characterized terrain → multiple operational zones → environmental context, with provenance, relationships and spatial indexes. Aircraft-independent knowledge is stored once and reused.

**Finished:** GeoPackage stage/final layers; parent candidate references; zone identifiers and metrics; maximum-clearance centre layer; GeoJSON/PNG/JSON exports; run logs/manifests; local temporal candidate GPKG/GeoJSON/CSV/metadata; canonical publication on Neha_branch.

**Remaining:** normalized persistent entities and keys; genuine terrain-to-slope-zone linkage; environment records; AOI/date/source-version indexing; constraints/referential integrity; selected-run contract; atomic publication of all companion artifacts; migrations/versioning; temporal correction/regeneration; no stale/failed run promotion.

**Status:** Useful GIS storage exists. The full planned Terrain Knowledge Database does not.

## Phase 6 — Helicopter recommendation engine

**Planned modules:** (1) aircraft inputs; (2) nearby zone retrieval; (3) weather and feasibility assessment with area/time reuse; (4) slope/surface/area/clearance compatibility; (5) landing footprint validation; (6) mission-aware ranking; (7) explained top-K recommendations.

**Finished prototype:** Dhruv, Prachand, LUH, Mi-17 and H135 profile configurations; custom overrides; immediate-emergency, safest, medevac and hybrid mission weights; coordinate/radius query; haversine distance/bearing; top-30 default results; rank numbers and weighted subscores; Open-Meteo data acquisition, daylight calculation, hourly interpolation including circular wind direction, recent/archive endpoint selection, retry/batch helpers, source metadata; weather/aircraft explanations and map cards.

**Remaining:** profile validation and traceable approved specifications; actual surface compatibility; measured slope matching; mandatory gates before preference ranking; exact footprint containment including holes; unknown-data policy; candidate/zone-specific weather coverage and persistent reuse; weather null/age/provider-failure handling; correct wind/approach conventions; road/rescue/environment inputs to mission ranking; duplicate-zone suppression; deterministic score semantics and proof fields; indexed retrieval and latency measurement.

**Confirmed defects:** slope is fabricated from clear diameter; a supplied 30° slope with a 10° configured limit still receives Optimal; missing weather receives a favourable default; adverse/incompatible sites are scored rather than consistently excluded. Profile surface lists are not implemented as surface checks. Medevac currently lacks measured road-access features.

**Status:** A visible querying/ranking prototype exists. The complete operational compatibility pipeline is pending.

## Phase 7 — User interface and integration

**Planned:** local integrated application connecting terrain knowledge and recommendation; maps, top-K results, explanation and source information.

**Finished:** original AOI/date/name upload interface, progress/logs, run history and downloads; loopback/file-access protection in original server; Neha's Flask weather/aircraft/mission console, satellite maps, colored polygons, ranked cards, dataset/reload endpoints and metadata endpoints.

**Remaining:** unify two servers and branch-specific features; preserve all rings and MultiPolygons in exports; consistent AOI/date/run selection across engine, map and metadata; automatic synchronized refresh; derive counts from real data; display unknown slope/surface honestly; imagery observation-date/registration information; distinguish all candidates from compatible ranked zones; fix errors/empty/stale states; recheck desktop/mobile/map performance; decide local-confidential operation versus external weather/map requests.

**Status:** Both interfaces exist, but a trustworthy integrated application is incomplete.

## Phase 8 — Optimization and enhancement

**Planned:** spatial indexing, fast recommendations, efficient storage, scalability, improved ranking and extensibility.

**Finished:** reusable modules, cached acquisition and offline outputs establish part of the foundation.

**Remaining:** spatially indexed candidate retrieval (current recommendation scans loaded zones); runtime/memory benchmarks; offline preparation optimization; bounded weather requests and caching; map loading/culling/simplification without changing authoritative geometry; incremental updates; clean installation and local package; consistent branch integration, source/data publication and deployment guidance.

**Status:** Foundations exist; measured optimization and deployment readiness have not been demonstrated.

## Cross-cutting validation and documentation

Original project work includes research papers/design documents, boundary diagnostics, archived restriction/obstacle experiments, synthetic unit/integration tests, Bhadra numerical audits and reference figures. These are substantial retained assets, not proof of complete operational functionality.

The current local suite passed 50 tests in the preceding review; updated Neha_branch passed 48. Suites cover different features. They are not directly comparable completeness metrics. Tests omitted real-state temporal negatives and polygon-hole fidelity.

The retained sample_01 validation package includes sample rasters, a boundary, QGIS project and annotation schema. Both `open_land_annotations` and `closed_land_annotations` contain **zero features**. Ground-truth preparation exists; this package does not supply completed labels or accuracy scores. Other transferred packages have not been established as validated ground truth.

Complete pending validation includes labelled candidates and missed locations; imagery/date alignment; spatial holdout evaluation; precision/recall where the labelled sampling permits; water/roof/vegetation-specific failures; slope and footprint checks; restriction audits; score tests; source-failure/unknown handling; performance and clean-install tests; mentor/domain review; versioned module metrics and acceptance criteria.

## Exact standing today

- Candidate-land research pipeline: implemented and reusable, with known coverage/accuracy limitations.
- Geometry and maximum clearance: implemented and internally audited.
- Historical processing: five dates processed; temporal evidence built but incorrect until repaired.
- Neha calibration: committed canonical dataset measures 2,484 zones and 36.683251 km²; code is present, but matching fresh exclusion inputs/run provenance are absent.
- Original June 1 result: 4,130 polygons, 88.824 km². March history: 8,275 polygons, 207.850 km². Different dates/rules must not be conflated.
- Terrain characterization, slope zones, environment, normalized DB: incomplete.
- Aircraft/weather/ranking/UI: prototype exists, ahead of the completeness of its terrain evidence.
- Complete planned HELPS system: not finished. There is no defensible numerical completion percentage.

## Design decisions that must be reconciled

1. Water: earlier context preserves labelled water for compatible aircraft; SDD obstacle definitions exclude it while its characterization section retains it; current detector excludes it. Resolve land-only V1 versus separate future water knowledge. Water must never be presented as open ground by accident.
2. Generic size policy: 900 m²/30 m preprocessing discards smaller sites before online evaluation, while some configured profiles request smaller footprints. Establish a documented universal minimum or preserve smaller terrain for later aircraft checks.
3. Operational-zone terminology: separate clearance-refined candidates from DEM slope-threshold zones.
4. Confidentiality: local server does not mean disconnected/local-only data processing when coordinates go to external weather services and basemaps are downloaded.
5. Research prototype claims: weights, counters and plausible labels must be distinguishable from measured physical evidence.

## Complete pending-task checklist

The ordering within a group is not a dependency graph. New feature design should resolve interfaces and acceptance criteria before implementation.

### A. Restore a coherent project baseline
- [ ] Reconcile the SDD, context notes, scope conflicts and phase naming.
- [ ] Inventory and safely integrate local history/temporal work with Neha's committed code.
- [ ] Keep both original and draft recoverable; record commits and selected data versions.
- [ ] Recover calibrated OSM/exclusion inputs, run manifest, summary, logs and hashes.
- [ ] Reconcile the 2,484/2,694/4,130/8,275 claims with dates and rule versions.
- [ ] Restore a complete reproducible dependency specification and clean-install check.
- [ ] Define evidence/status fields and phase acceptance criteria.

### B. Repair candidate and map reliability
- [ ] Preserve holes, MultiPolygons, CRS and geometry fidelity end to end.
- [ ] Add source-geometry/API/ranked-overlay regression checks.
- [ ] Select one completed, audit-passed run for all screens and engine queries.
- [ ] Publish/reload artifacts atomically and synchronously; protect against partial/failed runs.
- [ ] Replace hardcoded counts and fabricated terrain labels with actual fields.
- [ ] Fail closed on unreadable required exclusion layers.
- [ ] Audit water, industrial, buildings, cloud/UNKNOWN, mutual overlap and future restrictions independently.
- [ ] Establish imagery date/registration and vector coverage uncertainty.
- [ ] Reproduce the calibrated result using unchanged source inputs.

### C. Complete acquisition and obstacle policy
- [ ] Integrate DEM acquisition/preparation, units/datum/nodata/alignment checks.
- [ ] Establish authoritative restricted-area datasets, timestamps and exclusion policy.
- [ ] Integrate and audit restriction removal in supported processing.
- [ ] Establish tree/tower/pole/power-line/cliff obstacle treatment and missing-data limits.
- [ ] Validate canal width and shoreline setback policies against evidence.
- [ ] Version classification and exclusion rules; preserve rejection reasons and parent lineage.
- [ ] Define source completeness, freshness and refresh policy per AOI/date.

### D. Correct temporal evidence
- [ ] Use shared state constants and cover real NOT_OPEN=0 output in tests.
- [ ] Check/reproject CRS and distinguish unobserved/out-of-footprint evidence.
- [ ] Validate small-polygon pixel-area accounting and confidence/support semantics.
- [ ] Reprocess all comparison dates with consistent rules or explicitly version mixed evidence.
- [ ] Regenerate candidate database and invalidate obsolete confidence.
- [ ] Commit/document the finished local temporal work and registry policy.

### E. Finish characterization and slope zones
- [ ] Measure surface class/coverage and vegetation density.
- [ ] Store water descriptors and explicit uncertain surface/firmness evidence.
- [ ] Compute terrain elevation, slope raster, roughness and resolution uncertainty.
- [ ] Generate multi-threshold masks inside obstacle-cleaned terrain.
- [ ] Extract connected zones, handle nodata/slivers and preserve parent relationships.
- [ ] Recompute zone geometry, representative centres and MIC.
- [ ] Handle nested threshold duplicates and define query threshold selection.
- [ ] Measure road distance/connectivity and settlement/rescue context.
- [ ] Measure surrounding obstacles, water proximity and terrain-openness/approach context.

### F. Finish terrain knowledge storage
- [ ] Implement AOI/run/source, terrain, characteristics, zones and environment entities.
- [ ] Add temporal aggregates and links without conflating dates or duplicating geometry.
- [ ] Add referential integrity, unique keys, constraints and schema migrations.
- [ ] Add spatial/attribute indexes and explicit source/rule provenance.
- [ ] Implement coherent activation, refresh, versioning, backup and export.

### G. Finish recommendation logic
- [ ] Validate built-in/custom aircraft profiles and mandatory parameters.
- [ ] Retrieve compatible nearby zones using indexed spatial queries.
- [ ] Apply surface, measured slope, area, clearance and restriction hard gates before ranking.
- [ ] Validate actual footprint containment, including all exclusions/holes.
- [ ] Apply mandatory weather feasibility and explicit missing/stale-data policy.
- [ ] Establish weather coverage/time cache and candidate-area reuse rules.
- [ ] Correct/test wind direction and approach terminology; use measured context for approach score.
- [ ] Implement meaningful nearest/safest/hybrid/medevac/fuel priorities using stored evidence.
- [ ] Suppress duplicate threshold zones and define top-K/radius/empty-result behaviour.
- [ ] Define score normalization, weights, sensitivity, tie-breaking and confidence distinctions.
- [ ] Produce traceable proof and rejection reasons for every recommendation.

### H. Validate, integrate and deliver
- [ ] Complete the annotation campaign; check existing transferred packages before treating them as labels.
- [ ] Create a representative spatial holdout with negatives and missed candidates.
- [ ] Measure per-module and end-to-end performance with uncertainty and class-specific errors.
- [ ] Validate slope/footprint, restrictions, unknown-data and hard-gate behaviour.
- [ ] Unify AOI analysis, database selection, recommendation and map interfaces.
- [ ] Show source/date/version/confidence and measured versus unknown values clearly.
- [ ] Test empty/failed/stale runs, map refresh, responsive UI and accessibility.
- [ ] Benchmark query latency, preparation runtime, memory and map rendering.
- [ ] Optimize retrieval/storage/cache and implement incremental updates where justified.
- [ ] Decide external-service/confidentiality and disconnected-operation requirements.
- [ ] Update full SDD, schema, algorithms, module feasibility report, setup guide and limitations.
- [ ] Produce benchmark figures, final demonstration and mentor/domain review.
- [ ] Commit/integrate reviewed code, arrange bulk-data distribution and publish reproducible release artifacts.

## Deliberately separate future scope

Real-time onboard avionics/GPS integration, autonomous flight/landing, detailed flight-dynamics path planning, live detection of temporary obstacles, higher-resolution DSM/LiDAR inputs, fully validated amphibious/water landing support, nationwide coverage and advanced learned ranking are not implemented. The SDD explicitly excludes autonomous control, real-time satellite acquisition and direct avionics integration from V1. These must not be counted as missing mandatory V1 features unless the scope is formally expanded.

## Sources

- `docs/archive/HELPS_System Design Document.docx`: full roadmap and modules.
- `archive/project context.txt`: design philosophy/history and earlier unresolved research questions.
- `docs/archive/System Design Document.txt`: earlier outline and phase numbering.
- `docs/implementation-plan.md`: completed narrow AOI/date application milestone, not the full HELPS roadmap.
- `docs/code-responsibility.md` and README: implementation inventory, with some stale baseline descriptions.
- `docs/superpowers/plans/2026-09-14-temporal-candidate-database.md`: local temporal milestone.
- `HELPS-status-and-recovery-plan.md`, `audit-evidence.json`: current measured findings.
