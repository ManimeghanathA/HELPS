# HELPS V1 — complete original phases

Status: user-approved design implemented locally; delivery evidence and limitations are recorded in docs/v1-acceptance.md.

## Agreed purpose and boundary

The user explicitly requires every original terrain-analysis phase in V1. Completing only the current map/weather/ranking prototype is insufficient. HELPS must implement offline terrain knowledge generation and online helicopter-specific assessment, consistent with the original System Design Document.

Retain the broader Bhadra candidate map. The source has 2,484 polygons; seven existing reviewed quarantines leave 2,477 displayed. Preserve all original geometries and IDs as source references. The separate 191-candidate experiment is research evidence, not the selected replacement. Large improvements in obstacle detection and measured polygon accuracy are future scope by user instruction; their limitations remain visible in V1.

Candidates and operational zones are different entities. The broad terrain layer stays available even when a terrain object produces no slope/aircraft-compatible child zone. Such a result must explain the reason rather than silently deleting the parent from the map.

All eight implementation phases remain in scope:

| Phase | Current state | V1 deliverable and acceptance |
|---|---|---|
| 1. Geospatial infrastructure | Sentinel/vector inputs exist; prepared DEM has incomplete current-AOI coverage | Validated, versioned input package with full-area DEM, explicit restriction/context coverage, units/nodata/resolution/source dates and hashes |
| 2. Candidate terrain | Retained calibrated candidates and geometry-fidelity fixes exist; obstacle completeness unmeasured | Import/version retained terrain objects; preserve source IDs, full geometry and quarantine decisions; support auditable obstacle/restriction inputs |
| 3. Characterization | Geometry exists; most descriptive attributes absent | Surface proportions, vegetation indicators, water descriptors, elevation/slope/roughness, access and explicit unknown fields stored per terrain |
| 4. Operational zones | Geometry opening/MIC exist; real slope zones absent | Cell-level DEM derivatives, all documented slope thresholds, connected child zones, recomputed geometry/MIC, parent lineage and nodata handling |
| 5. Terrain knowledge database | Separate GIS outputs exist | Persistent normalized terrain/zone/context/source/run relationships, integrity checks, spatial indexes and an explicitly selected dataset |
| 6. Recommendation | Profiles/weather/weighted ranking exist; mandatory gates incomplete | Validated inputs, indexed retrieval, weather feasibility, measured slope/area/clearance matching, exact footprint containment, deduplication and explained top-K |
| 7. UI/integration | Candidate explorer and recommendation console exist; processing UI separate | One coherent workflow for datasets, candidates, slope zones, aircraft/mission/weather, results, explanations and exports |
| 8. Optimization | Basic offline reuse exists | Indexed queries, bounded/cacheable acquisition/weather, recorded performance, reproducible installation and regression/end-to-end checks |

Module implementation is distinct from physical/operational validation. V1 remains research decision support using available evidence and configurable research limits; it does not certify real-world landing clearance or legal permission.

## Chosen technical approach

Build the missing modules around the retained Bhadra terrain objects and existing Python/GeoPackage/Flask stack. Rebuilding candidate detection first would change the baseline and repeat the user's rejected coverage loss. Rewriting the entire application in another stack would add migration effort without supplying missing terrain knowledge. Neither is required for the chosen approach.

Keep offline preprocessing independent of aircraft profiles. Online queries consume precomputed features; they never calculate DEM derivatives or reclassify imagery during a request.

## 1. Input package and coverage contract

Each source record stores dataset identity, file hash, acquisition/reference date, CRS, extent, native and processing resolution, nodata, unit/vertical-datum status, coverage and limitations. A local filename is not sufficient proof of source identity.

Use a raw DEM covering the current AOI and an external derivative halo. The existing processed SRTM raster cannot be reused as-is: a read-only audit found 459 of the retained polygons outside its bounding box, approximately 37.51% valid coverage among intersecting DEM cells, and only 29.52% of retained polygon area covered by valid cells. Of the 2,477 retained objects, 1,654 have zero valid coverage in that old prepared DEM. The four raw tiles are valid, distinct arrays with complete retained-terrain extent coverage.

The proposed primary input for a noncommercial research build is the metadata-identified FABDEM v1-2, with NASADEM and Copernicus as disagreement diagnostics. Its embedded identity and [official dataset record](https://research-information.bris.ac.uk/en/datasets/fabdem-v1-2/) specify CC BY-NC-SA 4.0. Keep data licensing/attribution separate from code licensing and verify compatibility with intended distribution. Other raw-file edition/datum/source history is incompletely documented; do not infer it from filenames. Absolute vertical datum remains unverified; comparisons do not establish which terrain surface is physically correct.

Reproject elevation to a metric grid near its native scale. Do not describe a 30 m source interpolated to 10 m as independent 10 m terrain evidence. Check horizontal/vertical units before derivatives. Nodata and invalid derivative neighborhoods are withheld from operational-zone generation, never filled as flat terrain.

Restriction sources have an explicit supplied/unknown/verified-coverage state. Implement ingestion and geometric subtraction with source provenance and independent overlap audits. Do not infer aviation permission from a protected-area boundary, or represent absent restrictions as proven unrestricted airspace. No synthetic restriction fixture may become a live input.

Reuse supplied building, road, water and infrastructure layers, preserving source timestamps and coverage limits. Missing context produces null values and quality flags, not fabricated zero-distance/no-obstacle results. External-provider failures remain bounded and checkpointed.

## 2. Retained candidate objects and characterization

Import the accepted GeoPackage as a versioned candidate seed. Source polygons are already outputs of earlier geometry/clearance filtering; record that fact rather than claiming they reproduce the original raw connected components. Terrain identity is stable within the selected dataset, with a source-zone link and immutable geometry hash.

Store area, rotated-rectangle dimensions, bounding box and full Polygon/MultiPolygon geometry. Characterization enriches records without overwriting parent geometry.

Extract separately dated class proportions from current Sentinel/SCL evidence and historical WorldCover. Store valid sample counts and observable coverage. Vegetation fraction/index summaries describe evidence; they do not measure tree height or ground firmness. Surface categories must not equate a spectral bare-soil label with verified compact soil. Water descriptors combine supplied vector intersection/proximity and current spectral indications, with explicit conflicting/unknown evidence.

Measure elevation statistics, slope statistics, supported DEM coverage and a declared local roughness proxy. The roughness method and neighborhood size are versioned; no invented terrain values are permitted.

Accessibility contains geometric road distance, available access/type tags and source-supported connectivity. Geometric proximity does not establish vehicle access or rescue time.

Historical evidence remains separate and versioned. The corrected temporal database uses the original 4,130-candidate reference and must not be attached to these 2,484 source objects by ID or row order. Transfer requires an explicit spatial/date/source mapping and coverage audit.

## 3. Real slope and operational-zone generation

Compute slope with Horn 3×3 gradients on the metric elevation grid, withholding any incomplete neighborhood and the outer derivative edge. This is consistent with the no-edge handling described in [GDAL's slope documentation](https://gdal.org/en/stable/programs/gdal_raster_slope.html). Define roughness as detrended-plane residual RMS over the same declared neighborhood. Test analytic flat and inclined planes, nodata edges, unit conversion and raster alignment before applying it to Bhadra. Use four-connected slope components to avoid corner-only joins; preserve the existing terrain source topology separately.

Implement the SDD's research threshold collection: 0, 2, 4, 6, 8, 10, 12 and 15 degrees. These are precomputed analysis thresholds, not validated aircraft operating limits. Zero-degree results may legitimately be empty.

For each terrain object and threshold:

1. Intersect valid slope cells meeting the threshold with the terrain geometry and supplied obstacle/restriction masks.
2. Extract connected regions, preserving holes and splitting disconnected parts.
3. Apply versioned generic geometry gates; identify the reason for rejected fragments.
4. Recompute area, width/length, maximum-inscribed-circle centre/radius and slope statistics for every child.
5. Store the parent terrain ID, threshold, source/version and validity/coverage evidence.

Nested threshold zones may overlap by design. Audits prohibit inappropriate overlaps within the same threshold/parent partition, while checking cross-threshold lineage and monotonic inclusion. Do not apply the old global zero-overlap rule blindly across all thresholds.

Validate that child geometry is inside its parent, does not enter excluded/nodata cells, respects its threshold within declared numerical tolerance, and preserves all interior exclusions. The broad parent map remains available regardless of child count.

## 4. Environmental context

For each operational zone, compute nearest mapped road/water distances, available infrastructure/settlement context, surrounding mapped obstacle counts and source-supported cover fractions. Preserve missing coverage as unknown.

A versioned 200 m surrounding-area radius supports a 2D openness proxy derived from mapped obstacle/cover occupancy, with source coverage recorded and overlap counted once. Label it as environmental openness; without obstacle heights and flight dynamics it is not a validated approach corridor. Do not issue a guaranteed safe approach heading from a coarse wind vector.

Store context per zone, with provenance and analysis parameters. This supports medevac/access priorities and environment-sensitive ranking without making aircraft-specific changes to the terrain database.

## 5. Persistent knowledge and activation

Use GeoPackage/SQLite, retaining standard GIS-readable feature layers and normalized attribute tables:

- AOIs, dataset versions, analysis runs, source records and analysis parameters.
- Terrain feature layer with source identity and geometry.
- Terrain characteristics and observation-quality records.
- Operational-zone feature layer with parent ID, threshold and MIC centre/radius.
- Zone environmental context and threshold relationships.
- Optional versioned temporal observations and source links.

Unique keys, foreign-key checks, consistent units, spatial/RTree indexes and threshold/parent indexes are mandatory. Dataset creation writes to a staging package, verifies integrity and publishes an immutable package plus manifest.

Use an explicit selected dataset/AOI/date/version pointer. A newer completed run must not automatically supersede the user's retained map. Map, query engine, metadata and exports must use the same selected version. Activation/reload swaps a validated package coherently and preserves the previous one for recovery.

## 6. Aircraft/mission recommendation contract

Validate finite coordinates, radius/top-K, model/mission IDs and custom profile values. Unknown IDs and invalid limits produce explanatory input errors rather than silent default profiles. Existing built-in specifications are versioned research configurations; authoritative operational specifications remain a source-verification task.

Retrieve nearby operational zones using spatial indexes, choose supported slope thresholds compatible with the configured aircraft limit, then apply mandatory checks before scoring:

- Required weather fields, age/coverage policy and configured weather limits.
- Supported measured slope and DEM coverage.
- Minimum area and required clear diameter.
- Declared surface/restriction policy and unknown-evidence handling.
- Full required circular footprint containment in metric zone geometry, including holes and disconnected parts.

Failed or unknown mandatory evidence cannot receive a favourable suitability default. Keep candidate browsing available even when compatibility cannot be established. Every excluded/uncertain result carries explicit reasons. A research/exploratory result is distinguishable from passing configured checks.

Weather caching is keyed by location/declared spatial coverage, requested time, provider and retrieval age. Reuse never implies weather is constant across an entire AOI. Provider failures, stale records and unavailable fields remain visible.

Keep wind-from bearing, aircraft/approach heading and total wind speed as separate quantities. Crosswind assessment requires a declared heading; unavailable heading means unknown directional assessment. Validate provider snapshots on the server. Client-supplied weather is labelled user-supplied evidence and cannot claim verified provider identity merely through its JSON fields.

Rank only candidates that pass the selected policy. Mission scores use actual stored context: distance/estimated straight-line travel time, clearance, slope/roughness, surface evidence, access, water/obstacle context and modeled weather. Scores are relative priorities, not safety probabilities. Missing optional factors are omitted with documented normalization rather than awarded favourable values.

Suppress duplicate/nested-threshold recommendations for the same landing opportunity using a documented identity/overlap rule. Preserve explanations, factors, constraints, data dates and quality flags in top-K responses. An empty result includes failed-gate counts and retains an inspectable terrain layer.

## 7. Integrated application and reproducibility

The user clarified the application flow on 13 October 2026. The entry screen offers two roles: **Data Engineer** and **Application User**. Their navigation and workspaces differ, while both share the same published dataset and recommendation engine.

**Data Engineer workspace:** expose the offline workflow to acquire/import the required AOI data, inspect source completeness, execute all terrain-analysis phases, monitor stage progress/logs, inspect extracted features and operational zones, build/validate the knowledge database, and publish/select a dataset version. Include the same recommendation workspace available to Application Users so engineers can inspect the resulting behaviour. Failed or unfinished jobs cannot become published datasets.

The engineering form includes region/AOI and observation date, DEM selection, Sentinel spectral/SCL selection, OSM context, supplementary buildings, optional land-cover evidence and restriction inputs. Each source supports the applicable local-import or automatic-acquisition mode, with expected bands/layers, units, reference date, coverage and validation shown before execution. The retained Bhadra candidate layer is an explicit seed option. The UI must not suggest DEM analysis is running when the backend has only performed candidate classification/geometry extraction.

**Application User workspace:** expose recommendation and published-data exploration only. Do not show acquisition, pipeline execution, knowledgebase mutation or publication controls in this workspace. Role selection defines the local application workflow; deployment authentication/identity policy must not be claimed merely from hiding controls.

After selecting Application User, display the India map with all considered regions and a dropdown of regions with available published data. Bhadra is available initially. Planned regions are labelled as unavailable, with no fabricated polygon counts or processing status. Selecting Bhadra opens a dedicated region workspace inside the application. Keep region/dataset identity visible and provide navigation back to India or role selection.

The Bhadra workspace has three linked views:

1. **Recommendations.** Collect helicopter model/custom features, query coordinates, mission/context, time/weather inputs, search radius and top-K. Execute the full recommendation pipeline and display an ordered list with reasons. Selecting a recommendation focuses its actual operational-zone boundary on the map, shows the helicopter/query position and landing reference/footprint, and opens a reason panel beside the map. The panel includes mandatory-check results, measured characteristics, score contributions, evidence dates and unavailable/uncertain information. Preserve inputs and result selection when navigating between views.
2. **View Candidates.** Present the retained parent terrain polygons and their extracted features in a sortable/filterable/paginated table. Fields include identity, geometry metrics, supported surface/vegetation information, elevation/slope/roughness summaries, water/access context, child-zone availability and evidence quality. Selecting a row opens/focuses that polygon in the shared map and displays its feature badge/detail panel beside it. Unknown values remain unknown. Parent candidates remain inspectable even if no aircraft-compatible child exists.
3. **View Map.** Display all retained parent polygons. Selecting a polygon highlights its full boundary and displays the same feature panel used by table selection. Offer derived slope-zone/result overlays with explicit threshold/aircraft labels; they complement rather than replace the retained parent layer.

Slope visualization uses actual DEM-derived slope values. Provide a numeric degree legend with shades for the documented thresholds, a threshold selector and a distinct no-data/unsupported style. Parent terrain summaries and child operational-zone thresholds have separate labels: a whole polygon is not represented as uniformly flat merely because its mean is low. Selecting a parent shows min/mean/max slope and support/resolution; selecting a child shows its threshold and measured statistics. Where useful, display the slope raster to reveal variation inside a parent. Both role workspaces use the same versioned slope evidence and colors.

Use one shared selected-region/dataset/candidate/recommendation state and reusable map/detail components. A table row, recommendation item and polygon click must resolve to the same stored entity/version. Full Polygon/MultiPolygon rings and holes are preserved in every view. Prefer readable panels alongside the map; on narrow screens use an accessible drawer or stacked panel. Include clear loading, error, no-results and missing-feature states, keyboard-focus behaviour and return navigation.

Connect offline preparation/history/artifacts, selected knowledge version, aircraft/mission/time inputs, weather results, compatibility, ranked explanations and exports through the existing local application. Display genuine measured values or unknown status. Remove the diameter-derived slope and unmeasured surface labels.

Provide documented installation, required core/processing dependencies, one supported launch command, data-package requirements, a reproducible Bhadra build command, example inputs and a versioned result export. Do not require the private review dependency folder for the released setup.

Keep servers on loopback by default. Protect local run/activation/file APIs and export only published artifacts. Maintain archives and source recovery; no broad cleanup/deletion is part of this work.

## 8. Verification, performance and completion definition

Use meaningful analytic/geometry regressions: inclined/flat DEMs, nodata, threshold monotonicity, split/holey zones, footprint rejection, foreign-key failures, unknown/stale weather, hard-gate violations, profile validation and deterministic deduplication/ranking.

Run the entire Bhadra offline chain, inspect stored entities/source coverage and exercise online queries with controlled weather fixtures plus a real provider lookup when available. Tests must distinguish code correctness from source accuracy. No measured accuracy claim is allowed without an independent evaluation set.

UI acceptance includes both role entry paths, Data Engineer pipeline/progress/publication and recommendation access, the Application User India-to-Bhadra transition, top-K selection-to-map/reason navigation, candidate-table selection-to-map/features, direct polygon selection, consistent dataset identity, preserved user inputs and responsive detail panels. Application User navigation must not expose engineering mutations.

Record preprocessing runtime, database size, query latency, memory/map rendering and cache behaviour on this dataset. Optimize measured bottlenecks using spatial indexing and offline reuse; do not invent arbitrary national-scale performance promises.

V1 completion requires executable implementations and evidence for all eight phases, a populated Bhadra knowledge package, a coherent UI/query/export workflow, passing mandatory-gate/integrity tests, a reproducible setup and documented source/operational limits. Naming a stub module or returning a constant score does not complete a phase. External data gaps that prevent a required deliverable must be reported as remaining work.

## Future scope retained separately

Higher-resolution obstacle/canopy evidence, stronger polygon-classification calibration, independent physical-accuracy evaluation and ground validation; advanced height-aware approach modeling; nationwide coverage; live temporary-obstacle detection; onboard avionics integration and autonomous control. These do not excuse invented values or skipped V1 algorithms.

## Design review checkpoint

Review the retained-parent/derived-child model, source/unknown policies and phase acceptance table before implementation. After design approval, write the task-level implementation plan with dependencies and execution method. The approved implementation is delivered in the separate draft clone; acceptance evidence is recorded in docs/v1-acceptance.md.
