# HELPS status and recovery plan — 12 October 2026

HELPS has a working research pipeline, useful historical imagery, and a more developed decision-support UI. Neha's calibration materially reduces the candidate set. It still needs geometry-preserving map export, consistent run provenance, real terrain measurements, and independent labelled validation before its recommendations can be trusted.

## Versions reviewed

- Original local workspace: `Mani_branch`, commit `b187e6f`. Uncommitted README, historical search, temporal analysis, tests, and annotation packages were preserved.
- Separate clone: `HELPS - draft`, `Neha_branch`, commit `236c34c`, pulled by fast-forward from `5604351`.
- Common code baseline: `edf92f4`. The branches contain different additions: local historical workflows versus Neha's weather, aircraft profiles, ranking, Flask UI, calibration, and canonical publication.
- No merge, push, threshold edit, or production code fix was performed during this review. Review artifacts live beside the original workspace documentation.

## Where the project stands

The established pipeline validates AOI/date, acquires or reuses Sentinel-2 L2A plus OSM/Overture inputs, classifies possible-open pixels, polygonizes them, subtracts obstacles, applies geometry and clearance gates, audits the output, and exports GIS data and imagery.

The local branch also has five processed historical dates and a 4,130-candidate temporal database. Neha's branch adds a satellite map, point/weather lookup, helicopter profiles, mission weights, and candidate ranking. These are separate application paths: `scripts.ui.server` runs the original AOI pipeline interface; `app.py` runs the new Flask decision console. They are not yet one fully integrated application.

| Dataset or claim | Count | Area | Evidence |
|---|---:|---:|---|
| Original June 1 reference | 4,130 | 88.824 km² | Local and committed reference summary |
| Local October 12, 2025 history | 949 | 4.430 km² | Retained historical summary |
| Local December 11, 2025 history | 2,720 | 32.635 km² | Retained historical summary |
| Local February 4, 2026 history | 5,553 | 96.299 km² | Retained historical summary |
| Local March 26, 2026 history | 8,275 | 207.850 km² | Retained historical summary |
| Local May 15, 2026 history | 3,558 | 97.724 km² | Retained historical summary |
| Updated canonical June 1 GeoPackage | **2,484** | **36.683251 km²** | Direct measurement in this review |
| Updated Flask region counter | 2,694 | — | Hardcoded value; inconsistent with loaded data |
| Screenshot original baseline | ~8,275 | ~118.4 km² | Cannot reconcile with a retained matching run |

Do not describe the reduction as a measured number of false positives removed. Rejected candidates have not all been independently labelled. June 1's retained 4,130 baseline, March's 8,275 result, and the screenshot's 8,275/118.4 figure cannot be treated as equivalent runs without manifests and input hashes.

## What Neha actually changed

Confirmed in the latest source:

1. SCL 5 bare ground keeps NDVI ≤ 0.50; SCL 4 vegetation now requires NDVI ≤ 0.20.
2. OSM acquisition adds industrial/construction/quarry/landfill/farmyard exclusions and checks required layer names before reusing OSM files.
3. Water and industrial layers are passed through subtraction. Water lines receive a 5 m buffer and all resulting water geometry receives an additional 20 m setback.
4. Completed pipeline GeoPackages are copied into the canonical area/date location.
5. Flask adds `/api/pipeline-zones`, `/api/pipeline-run-info`, `/api/reload-zones`, and `/api/gpkg-zones`; the new map loads candidate annotations over Esri imagery.
6. Building-overlap audit tolerance becomes 1e-4 m². The original local workspace already uses this tolerance for its historical workflow.

The 900 m² area gate, 30 m dimensions, 15 m erosion/reconstruction, maximum-inscribed-circle calculation, and 30 m cloud buffer are retained mechanisms, not newly introduced algorithms. MNDWI < 0 and explicit SCL-water rejection also existed previously. The active state encoding remains **NOT_OPEN=0, POSSIBLE_OPEN=1, UNKNOWN=255**, unlike the screenshot's 0/1/2 description.

## Confirmed problems and their implications

### 1. Map export fills excluded polygon holes — first priority

`landing_zone_engine.py:110` manually parses only the exterior ring of each Polygon. It does not preserve interiors and does not support MultiPolygon WKB. `app.py:229` reconstructs GeoJSON from that exterior alone. The ranked overlay in `static/app.js` also uses the exterior list.

The new canonical file contains 122 polygons with 297 interior holes, totalling **472,555.271 m²** of excluded interior area. Those holes may represent buildings or other rejected terrain; their individual causes have not all been labelled. The exterior-only export fills them all back in.

Reproduced using `Bhadra_ZONE_000007`: stored geometry has one hole; the actual fallback API response has one exterior ring only. Its exported shape adds **907.712 m²** beyond the stored candidate, with another **11.924 m²** omitted through coordinate conversion/rounding differences. See `polygon-hole-reproduction.png`.

This explains a concrete class of apparent map/building inconsistencies. It does not prove every reported inconsistency has this cause. A direct run GeoJSON preserves holes; the fallback GeoPackage export and ranked-site overlay do not. A fresh clone has no run folder and therefore uses the affected fallback.

### 2. Slope is invented from clearance; ranking does not enforce slope limits

`landing_zone_engine.py:249` computes slope from clear diameter. It never samples the DEM. `static/app.js:708` describes missing slope as “Flat / Low.” Neither is evidence of flat ground.

Reproduction: an explicitly supplied 30° slope with a 10° aircraft limit still returns **Optimal**, score **92**, because excess slope only lowers an area subscore. Clearance, distance, and default weather compensate. Unknown weather starts at a score of 90. Aircraft limits and mission weights are configured heuristics, not validated operational rules. The wind approach text also adds 180° to a wind-from direction; its terminology and vector convention need review before being shown as guidance.

### 3. No single authoritative run is shared by the map, engine, and metadata

The engine chooses the newest directory with a GeoPackage. The polygon endpoint independently chooses the newest directory with GeoJSON. The info endpoint independently chooses the newest directory with `run.json`. None requires `status=complete` and a passed audit. Files from a partial/failed run, or different AOIs/dates, can consequently be combined. The engine loads once until explicitly reloaded; browser annotations load during map initialization.

Publication copies only the GeoPackage, without a matching manifest/summary, and is not always atomic (`copy2` is tried first). Dataset freshness and consistency need an explicit selected-run contract.

### 4. Exact calibration provenance and exclusion inputs are missing

The committed OSM file has `buildings`, `roads`, `power`, `man_made`, `water_polygons`, and `barriers`. It lacks the required `water`, `industrial`, and `railways` layers. The new completeness check appropriately forces reacquisition, but the exact OSM inputs that produced 2,484 candidates are not in this checkout. Run folders and input manifests are ignored by Git.

`docs/results/bhadra_summary.json` still describes 4,130 candidates. The UI says 2,694. The fallback run-info API returns `no_runs`. The screenshots' 90 water features, five industrial sites, and 33,896 buildings are not independently established from a matching run package. The committed sources contain 28 OSM building features and 33,867 Overture features before any repair/explosion.

The exclusion reader catches arbitrary read errors and returns an empty layer. Completeness acquisition helps with missing layer names but does not make this later read fail closed. The final audit is passed only building geometry and has no independent vector water/industrial overlap checks.

### 5. Local temporal evidence ignores the actual negative class

The uncommitted `scripts/temporal_analysis.py` excludes state 0 when counting not-open area, even though the active detector writes NOT_OPEN=0. Its tests use state 2 instead, so the local suite passes without covering real detector output.

Reproduction: raster `[[1,0],[0,255]]` gives 100% temporal confidence; the expected observable-area ratio is 1/3. The existing temporal database must be treated as invalid pending correction and regeneration. Also validate/reproject raster CRS before overlay, distinguish out-of-footprint pixels from negative observations, and document pixel-centre discretization for small candidates.

### 6. Spatial accuracy and semantic accuracy remain unmeasured

Pixel-centre audits, valid polygons, obstacle subtraction, and clearance circles demonstrate internal consistency. They do not measure whether real land is water, a roof, scrub, mud, or genuinely usable ground. Missing OSM/Overture features can still pass.

Sentinel B11 and SCL have native 20 m resolution even when exported on a 10 m grid. Resampling does not create building-level detail. Esri imagery may depict another date; the current UI does not establish a matched observation date or alignment accuracy. These are hypotheses to investigate for residual errors, not confirmed explanations for specific sites.

## Verification completed

- Updated branch: **48 tests passed** with isolated Flask/Astral/Fiona review dependencies and unrestricted localhost/temp-file access.
- Original local workspace in the preceding review: **50 tests passed** outside sandbox restrictions. Its temporal tests have the encoding coverage gap above.
- Measured updated GeoPackage: 2,484 Polygon features; all geometries valid; no zone pairs overlapping by more than 1e-6 m².
- Against the committed building sources: cumulative overlap **1.7053e-6 m²**, below the configured 1e-4 tolerance. This is negligible relative to the rendering error; it does not support a claim of building-level real-world completeness.
- Reclassified committed imagery using the updated detector plus three-pixel cloud buffer: zero candidate pixel centres in UNKNOWN, NOT_OPEN, or SCL water.
- Exercised actual Flask fallback endpoints: 2,484 features loaded, discarded interior ring reproduced, region counter 2,694, no run manifest available.
- Saved read-only audit script, machine-readable evidence, and a visual reproduction in this directory.

A full acquisition-to-output rerun was not performed. The exact calibrated exclusion inputs are absent, and a new OSM query would be a new snapshot rather than a reproduction of Neha's run. The current `requirements.txt` lists only requests, astral, and Flask; it omits the geospatial pipeline and test dependencies. Test success used the existing geospatial environment, not a clean installation from that file.

## Next tasks, in execution order

| Order | Task | How to complete it | Acceptance condition |
|---|---|---|---|
| 1 | Preserve geometry in every map path | Read GPKG using a standard geometry library; export full WGS84 GeoJSON including interiors and MultiPolygons; use it for both full-map and ranked-site layers | Round-trip/API tests preserve all rings and components; example excluded interior remains unfilled |
| 2 | Make every screen use one verified dataset | Select an explicit run/AOI/date; require complete status and passed audit; atomically publish GPKG, GeoJSON, summary, provenance; reload engine and map together; derive counters from data | Map, ranking, count, and metadata identify the same run; failed/partial runs never become active |
| 3 | Establish a reproducible calibrated baseline | Obtain Neha's exact input manifest, OSM file, run JSON, summary, logs, and checksums; restore complete dependency specification; rerun unchanged inputs | Count and area differences are explained; water/industrial exclusions have recorded source counts and independent overlap audits |
| 4 | Repair temporal scoring | Use the shared enum constants, test real state-0 negatives, check CRS/coverage, regenerate evidence with one consistent detector configuration across dates | Mixed open/non-open example yields 1/3; obsolete confidence values replaced with versioned results |
| 5 | Build a labelled error benchmark | Review roughly 100–200 stratified candidates across roofs, water margins, canals, fields, scrub, small/large zones; add labelled missed open sites and matched imagery dates; keep spatial holdout areas | Report candidate precision, labelled-missed-site recall where meaningful, class-specific failures, and reviewer disagreement |
| 6 | Calibrate from the benchmark | Compare class thresholds, water setbacks, building uncertainty margins, and temporal rules on development samples; retain rejection reasons | Held-out performance improves without hiding water/building errors through average scores |
| 7 | Measure terrain and enforce feasibility | Sample DEM and quantify coverage/resolution; mark unknown slope explicitly; apply validated hard constraints before mission ranking; separate candidate evidence from operational judgement | Unknown/over-limit terrain cannot be labelled Optimal; any aircraft rules have traceable approved sources |
| 8 | Integrate and package the project | Combine AOI processing and decision UI against the same run contract; retain both branches' useful work; document setup, limitations, provenance, and evaluation | Clean installation works; end-to-end regression and held-out benchmark pass |

Start with map fidelity and provenance before adjusting thresholds again. Otherwise display errors and stale datasets can be mistaken for classification failures. The target is an explainable candidate-ground research system with measured reliability; helicopter suitability requires additional terrain, obstacle, aircraft, permission, and field evidence.

## Technical sources

- [Copernicus Sentinel-2 L2A band and SCL resolutions](https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Data/S2L2A.html)
- [Shapely Polygon interiors](https://shapely.readthedocs.io/en/stable/reference/shapely.Polygon.html)
- [Shapely geometry mapping](https://shapely.readthedocs.io/en/stable/manual.html)
