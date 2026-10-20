# Reliability milestone — 13 October 2026

The first two confirmed defects have been corrected locally. This completes map-geometry fidelity and negative-class temporal accounting, not the full HELPS system.

## Map geometry

Changes are in `HELPS - draft` on top of Neha_branch commit `236c34c`.

- The landing engine reads GeoPackage layers through GeoPandas, uses the actual source CRS, and preserves all Polygon/MultiPolygon rings and parts without rounding vertices.
- Engine records carry complete WGS84 GeoJSON geometry. The existing Leaflet coordinate field also retains complete rings/parts.
- `/api/gpkg-zones` returns that geometry unchanged.
- Ranked map overlays use `L.geoJSON`; missing geometry is no longer displayed as an apparently usable bounding rectangle.
- The application requirements now include GeoPandas and Shapely.

Actual dataset verification: 2,484 exported features, all 297 interior rings retained. Maximum round-trip symmetric difference per zone is approximately 8.64e-7 m². Across all zones it is approximately 1.31e-4 m², from projection roundoff.

Regression coverage includes excluded interiors, disconnected polygon parts, EPSG:32643 and EPSG:32644 source data, both map and ranked endpoints, and the browser renderer's Leaflet boundary. The JavaScript tests failed against the previous committed renderer and pass against the correction. They do not replace a full interactive browser review.

## Temporal evidence

Changes are in the original local workspace's previously uncommitted temporal module and tests. Pre-edit copies were saved under this directory's `backups` folder.

- Both individual and labelled-raster aggregation use the detector's shared constants: NOT_OPEN=0, POSSIBLE_OPEN=1, UNKNOWN=255.
- Previous fixtures using the wrong non-open encoding were corrected.
- The regression example `[[1,0],[0,255]]` now gives confidence 1/3 and support 0.75, excluding UNKNOWN from the confidence denominator.

Regenerated files are stored separately at:

`data/processed/Bhadra/candidate_database/2026-06-01-corrected-2026-10-13/`

The original outputs remain available for comparison and should not be used as trustworthy confidence results.

This regeneration uses the original local **4,130-candidate** June 1 reference and its five original historical masks. It does **not** score Neha's calibrated 2,484-candidate dataset. Reprocessing dates with the calibrated rules and consistent source provenance remains pending.

Before correction every stored confidence was 1.0. Afterwards the median is approximately 0.5286; 4,082 candidates are below 1.0. These values measure historical open-surface evidence under the existing detector, not ground-truth accuracy or landing safety.

## Verification

- Original Python suite: **51 passed**.
- Draft Python suite: **52 passed**.
- Node renderer tests: **3 passed**.
- JavaScript syntax and Git whitespace checks passed.
- A read-only independent reviewer found no critical or important correctness issues in the scoped changes. The reviewer could not rerun tests with the draft's unused virtual environment; runtime evidence is from the verified commands below.
- Source imagery and authoritative polygon datasets were not changed. No commit, push or merge was performed.

Reproduce tests from the original project root:

```powershell
.\helps_env\Scripts\python.exe -m pytest -q
```

From `HELPS - draft`, using the isolated review dependencies installed during the audit:

```powershell
$env:PYTHONPATH = Join-Path (Get-Location) '.review-deps'
..\helps_env\Scripts\python.exe -m pytest -q
node --test tests/test_map_geometry.cjs
node --check static/app.js
```

Local HTTP/temp-file integration tests need an environment allowing loopback connections and temporary file replacement. The verified full suites were run outside those sandbox restrictions. Clean installation and full dependency packaging remain separate pending work.

Machine-readable real-data evidence is in `reliability-evidence.json`.

## What remains next

The next reliability milestone is one selected, completed, audit-passed dataset shared by map, engine, counters and metadata, with consistent publication/reload. Current run selection and hardcoded counters remain unchanged.

Measured slope, surface compatibility, mandatory aircraft/weather gates, exact footprint validation, labelled ground truth, restrictions and broader terrain characterization remain outstanding. The geometry fix does not establish that candidate surfaces are physically landable.
