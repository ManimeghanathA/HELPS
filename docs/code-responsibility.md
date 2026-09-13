# Code Responsibility

This document explains the active HELPSs code after the cleanup. Archived files are preserved as research history, but the files below are the supported project surface.

## Main Entry Points

### `scripts/pipeline/run_aoi_pipeline.py`

Command-line and UI pipeline entry point.

Responsibilities:

- Reads `--aoi`, `--date` and `--name` from the CLI.
- Validates the AOI and builds the geometry/date cache key.
- Creates one independent run folder under `data/runs/<run_id>/`.
- Runs the active pytest suite before processing.
- Calls acquisition for Sentinel, OSM and Overture inputs.
- Merges OSM building features and Overture building features.
- Calls the processing orchestrator.
- Writes `run.json` and `run.log`.
- Marks the run as `complete` or `failed`.

Use this file when running HELPSs without the UI:

```powershell
python -m scripts.pipeline.run_aoi_pipeline --aoi "data/raw/Bhadra/bhadra_entire_region.geojson" --date 2026-06-01 --name Bhadra
```

### `scripts/ui/server.py`

Local browser application server.

Responsibilities:

- Serves the UI on `127.0.0.1`.
- Accepts uploaded GeoJSON AOIs through `/api/run`.
- Starts the same pipeline used by the CLI.
- Tracks current run status and log messages in memory.
- Lists previous completed or failed runs through `/api/runs`.
- Serves only approved final artifacts from `data/runs`.
- Rejects non-loopback hosts, cross-origin requests and arbitrary file access.

Use this file when running HELPSs with the UI:

```powershell
python -m scripts.ui.server --port 8765
```

## Pipeline Package

### `scripts/pipeline/inputs.py`

AOI validation and cache identity.

Responsibilities:

- Defines the repository root.
- Creates data directories and their sibling `archive` folders.
- Loads AOI GeoJSON files with GeoPandas.
- Requires a CRS, non-empty valid geometry and Polygon/MultiPolygon features.
- Reprojects AOIs to WGS84.
- Rejects AOIs outside supported longitude/UTM latitude bounds.
- Rejects very large regional extents above six degrees.
- Normalizes geometry and date into a stable cache key.
- Detects the known Bhadra AOI/date and maps it to retained local source data.

### `scripts/pipeline/acquisition.py`

Input acquisition and input caching.

Responsibilities:

- Computes SHA-256 checksums for source data.
- Writes JSON manifests atomically.
- Reuses verified cached source files when checksums match.
- Downloads Sentinel-2 L2A spectral bands and SCL through the Copernicus Process API.
- Tiles large AOIs into 10 m UTM requests, mosaics the tiles and clips to AOI.
- Queries OSM groups for buildings, roads, railways, power, man-made features, barriers and water.
- Stores OSM groups as GeoPackage layers.
- Downloads Overture building footprints using the `overturemaps` CLI.
- Saves acquisition manifests under `data/inputs/<key>/<date>/manifest.json`.

Important note: OSM and Overture are current acquisition-time snapshots. They are not historical snapshots from the Sentinel observation date.

### `scripts/pipeline/processing.py`

End-to-end processing orchestration after inputs exist.

Responsibilities:

- Checks Sentinel rasters are projected, aligned and 10 m.
- Fails closed if the AOI/date has no observable Sentinel pixels.
- Generates the possible-open raster with the 30 m cloud buffer.
- Polygonizes open raster components.
- Makes building geometries valid and subtracts them exactly.
- Applies candidate geometry thresholds.
- Extracts independent operational zones using the 15 m clearance operation.
- Applies a second geometry gate to child zones.
- Measures maximum inscribed-circle diameter.
- Audits final zones for cloud/UNKNOWN overlap, building overlap, zone overlap, valid geometry, ID uniqueness and stored-area consistency.
- Writes `summary.json`, `final_zones.gpkg`, `final_zones.geojson` and `final_zones.png`.
- Stores intermediate masks and vector stages under the run folder's `archive`.

## Processing Algorithms

### `scripts/processing/open_land_detector.py`

Raster classification logic.

Responsibilities:

- Defines state values: `0 = NOT_OPEN`, `1 = POSSIBLE_OPEN`, `255 = UNKNOWN`.
- Computes normalized differences safely.
- Computes NDVI and MNDWI from Sentinel bands.
- Implements the retained V2 possible-open rule:
  - observable SCL class,
  - not explicit water,
  - `NDVI <= 0.50`,
  - `MNDWI < 0`.
- Marks cloud, shadow, nodata, snow, defective and unclassified SCL pixels as UNKNOWN.
- Expands cloud and cloud-shadow pixels by a configurable pixel buffer.
- Writes the classified possible-open GeoTIFF.

### `scripts/processing/candidate_polygonization.py`

Raster-to-vector conversion.

Responsibilities:

- Takes the possible-open raster state array.
- Extracts connected `OPEN = 1` raster regions using 8-connectivity.
- Converts connected regions into polygon geometries.
- Returns one GeoDataFrame with a `component_id` per open component.

### `scripts/processing/building_subtraction.py`

Building footprint removal.

Responsibilities:

- Aligns building CRS to the open-land CRS.
- Merges building footprints into one union geometry.
- Subtracts that union from every open-land component.
- Splits MultiPolygon and GeometryCollection results into usable polygon fragments.
- Preserves empty outputs correctly when buildings remove all open land.
- Emits progress messages during large full-AOI runs.

### `scripts/processing/candidate_geometry_filter.py`

Basic candidate size and shape measurements.

Responsibilities:

- Measures polygon area.
- Uses the minimum rotated rectangle to estimate candidate length and width.
- Applies the retained geometry gate:
  - area at least `900 m2`,
  - length at least `30 m`,
  - width at least `30 m`.

### `scripts/processing/clearance_analysis.py`

Clearance-core helper.

Responsibilities:

- Erodes candidate polygons inward by a clearance radius.
- Returns surviving internal clearance cores.
- Handles Polygon, MultiPolygon and GeometryCollection outputs.

This file is retained because it is useful for tests and explanation, even though the main pipeline now uses `operational_zone_extraction.py` for final zone reconstruction.

### `scripts/processing/operational_zone_extraction.py`

Narrow-neck removal and operational-zone reconstruction.

Responsibilities:

- Erodes the full candidate by the required clearance radius.
- Removes narrow corridors and necks that cannot preserve clearance.
- Dilates the surviving geometry back once.
- Clips reconstruction to the original candidate.
- Returns disconnected usable polygon zones without overlapping child reconstructions.

The main pipeline uses a 15 m radius, which corresponds to the retained 30 m clear diameter requirement.

### `scripts/processing/maximum_clearance.py`

Maximum inscribed-circle measurement.

Responsibilities:

- Uses Shapely `polylabel` to find an approximate point of maximum internal clearance.
- Measures distance from that point to the polygon boundary.
- Reports radius and diameter in metres.
- Handles MultiPolygon defensively by choosing the part with the largest radius.

Final zones must have a maximum clear diameter of at least `30 m`.

## Validation

### `scripts/validation/candidate_cloud_audit.py`

UNKNOWN-overlap audit helper.

Responsibilities:

- Rasterizes candidate zones back onto the Sentinel grid.
- Counts UNKNOWN pixels whose centres fall inside the zones.
- Counts how many individual zones touch UNKNOWN pixel centres.
- Uses the pixel-centre rule to avoid false positives from boundary-only contact.

The final pipeline has a broader audit inside `scripts/pipeline/processing.py`, but this helper remains useful and tested.

## UI Files

### `scripts/ui/index.html`

HTML shell for the local UI.

Responsibilities:

- Defines the AOI upload form.
- Defines the date and name fields.
- Defines status, metrics, map preview, logs and download areas.

### `scripts/ui/style.css`

Visual styling for the local UI.

Responsibilities:

- Provides the responsive two-column desktop layout.
- Provides compact mobile layout behavior.
- Styles the form, run history, status markers, metrics, map and logs.

### `scripts/ui/app.js`

Browser-side UI behavior.

Responsibilities:

- Reads the selected GeoJSON file.
- Sends the AOI, date and name to `/api/run`.
- Polls `/api/state` and `/api/runs`.
- Renders run status, progress logs, summary metrics and artifact links.
- Displays `final_zones.png` for completed runs.
- Handles common upload and server errors in the page.

## Maintenance Script

### `scripts/organize_workspace.ps1`

One-time cleanup migration script.

Responsibilities:

- Documents the project cleanup rules that were applied.
- Archives obsolete scripts, superseded data and old research files.
- Deletes only explicitly listed obsolete generated masks and overlays.
- Creates `archive` folders inside active data directories.
- Writes `docs/cleanup-manifest.json`.
- Refuses to run after the manifest exists, so it is not a normal development command.

## Tests

### `tests/test_open_land_rules.py`

Tests possible-open classification rules, UNKNOWN handling and Sentinel SCL behavior.

### `tests/test_open_land_raster.py`

Tests raster reading, output writing and possible-open mask generation.

### `tests/test_candidate_polygonization.py`

Tests conversion from open raster pixels to vector polygon components.

### `tests/test_building_subtraction.py`

Tests building removal behavior, split fragments and all-removed empty outputs.

### `tests/test_candidate_geometry_filter.py`

Tests area, length, width and threshold gating.

### `tests/test_clearance_analysis.py`

Tests inward clearance-core extraction.

### `tests/test_operational_zone_extraction.py`

Tests final operational-zone extraction and narrow-neck behavior.

### `tests/test_maximum_clearance.py`

Tests maximum clear-radius and clear-diameter measurement.

### `tests/test_candidate_cloud_audit.py`

Tests UNKNOWN pixel overlap auditing.

### `tests/test_pipeline.py`

Tests pipeline-level AOI validation, cache keys, empty-output behavior and synthetic end-to-end processing outputs.

### `tests/test_acquisition.py`

Tests acquisition reuse, checksum behavior and partial-stage checkpoint behavior with mocked inputs.

### `tests/test_download_adapters.py`

Tests Sentinel acquisition request/response handling with mocked TIFF responses.

### `tests/test_ui_server.py`

Tests local UI server endpoints, run listing and artifact access restrictions.

## Archived Code

`scripts/archive/` contains old runners, diagnostics, boundary experiments, earlier visualization scripts and superseded tests. They are intentionally kept for GitHub history and project traceability, but they are not the supported way to run HELPSs now.

Supported execution should go through either:

```powershell
python -m scripts.pipeline.run_aoi_pipeline --aoi "<aoi.geojson>" --date YYYY-MM-DD --name "<name>"
```

or:

```powershell
python -m scripts.ui.server --port 8765
```
