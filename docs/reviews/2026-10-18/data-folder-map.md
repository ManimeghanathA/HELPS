# HELPS data folders and code connections

Inspected 18 October 2026 in the canonical `HELPSs` workspace. Inventory includes nested archives and generated test files; sizes are approximate GiB. No source data was moved or deleted. Machine-readable counts are in `data-folder-inventory.json` beside this document.

## Current selection

`data/knowledge/registry.json` selects `bhadra-v1-20260601-fabdem-20261013`. Main version-bound map, candidate and recommendation APIs read its `knowledge.gpkg` through `scripts/ui/api.py` and `scripts/knowledge/repository.py`. It contains 2,477 parent polygons and 13,150 measured slope subregions. It does not yet contain the new normalized temporal tables.

`data/knowledge/bhadra-temporal-580354150707/knowledge.gpkg` is the completed geometry-preserving enrichment, with five historical dates and 78,135 dated observations. Its job is pending review; it is not published or selected. Folder existence alone does not activate a package.

## Folder inventory

| Folder | Files | GiB | Actual contents and code connection |
|---|---:|---:|---|
| `data/raw` | 104 | 2.232 | Original Sentinel material under six dated folders; four DEM rasters; authoritative Bhadra AOI and reviewed exclusions. `pipeline/inputs.py` validates AOIs and locates known baseline sources. `pipeline/elevation.py` checks the known FABDEM. The reviewed exclusions also feed candidate generation and legacy map loading. `raw/OSM` is empty. |
| `data/processed` | 99 | 1.629 | Bhadra spectral/SCL rasters, masks, saved polygons, previews and provenance for five historical dates plus June 1. Also OSM context GeoPackage, Overture building GeoJSON, processed SRTM, two candidate-database exports and archives. `pipeline/inputs.py` recognizes June 1 legacy inputs; `knowledge/temporal.py` discovers dated history; the Bhadra source catalog references these inputs. |
| `data/inputs` | 107 | 2.277 | Acquisition caches keyed by normalized AOI geometry **and observation date**, including manifests, cropped imagery, context files and source-tile archives where present. `pipeline/acquisition.py` reuses checksum-matching files and validates OSM layer completeness. One folder currently contains only a manifest, illustrating that a folder is not proof of a completed acquisition. |
| `data/knowledge` | 99 | 0.846 | Selected package, pending enrichment, build logs/checkpoints/rasters, registered sources, persisted jobs, history reclassification cache, monthly search cache and quality cache. Also a small invalid-DEM acceptance-test artifact. `knowledge/build.py`, `knowledge/enrichment.py`, `knowledge/review.py` and UI services manage this workflow. |
| `data/runs` | 82 | 0.926 | Twelve older polygon-run directories: seven complete, five failed. Run metadata/logs, AOI, final polygons, summaries and intermediate archives. `pipeline/run_aoi_pipeline.py` writes these; `pipeline/run_selection.py` and legacy `LandingZoneEngine` select eligible completed outputs. They are not the current knowledge registry. |
| `data/uploads` | 0 | 0 | Empty apart from an empty archive directory. Older `scripts/ui/server.py` stages AOI uploads here. Current source upload API stores files in `data/knowledge/sources`; registered region boundaries use `data/knowledge/regions`. |
| `data/cache` | 23 | 0.008 | OSMnx request cache, a small verified elevation smoke-test cache, and old server logs. `pipeline/acquisition.py` sets the OSMnx cache path; `pipeline/elevation.py` validates elevation manifests, checksums, grids, units and coverage before reuse. |
| `data/experiments` | 12 | 0.009 | One Bhadra land-cover screening experiment, written by the experiment script under `docs/reviews/2026-10-13`. Its outputs are not selected production knowledge. |
| `data/validation` | 4,874 | 0.415 | Original Bhadra validation material and archived annotations, plus generated test databases/rasters, regression workspaces and test logs. Tests use isolated locations here. These are not production recommendations; not everything here is disposable because original annotations are mixed with generated fixtures. |
| `data/archive` | 36 | 1.428 | Workspace migration/recovery snapshots, Git bundles, acquisition smoke evidence and current runtime logs. Recovery material explains and protects the earlier consolidation. |

Total: approximately **9.77 GiB**, including all nested archives. Empty `archive` directories are also created by `pipeline/inputs.py:data_directory`; they are intentional scaffolding, not additional datasets.

## Modern knowledge flow

1. Register a region boundary and sources through `scripts/ui/unified_api.py` / `scripts/ui/api.py`. Upload assets and `.asset.json` records live under `data/knowledge/sources`; new region boundaries/records live under `data/knowledge/regions` and `regions.json` when registered.
2. Resolve selected sources, known baseline files, acquisition cache and elevation cache. Download required missing sources through `scripts/pipeline/acquisition.py` and `elevation.py`.
3. `scripts/knowledge/build.py` generates candidates or loads an explicit retained seed, then measures terrain, extracts slope zones, calculates environmental and temporal features, and writes `data/knowledge/<dataset_id>`.
4. Package contents include `terrain`, `zones`, `terrain_characteristics`, `zone_environment`, `lineage`, source/provenance tables and metadata. New temporal packages additionally contain normalized dated observations and aggregates. Raster derivatives live beside the package in `rasters`; enrichment can reference preserved original rasters.
5. Persist progress/decision in `data/knowledge/jobs/<job_id>.json`. Completed packages remain pending. The review API supplies the proposed map and counts.
6. Only explicit reviewed acceptance registers/selects the package in `registry.json`. Current version-bound map/table/recommendation requests use that published package.

## Historical data and older paths

Historical observation dates are 2025-10-12, 2025-12-11, 2026-02-04, 2026-03-26 and 2026-05-15; June 1 is the current reference. `processed/Bhadra/sentinel2/history_dates.json` indexes these original observations. Current temporal calculations read and harmonize classification evidence, then measure overlap against each retained entity. Older exported `candidate_database` CSV/GeoJSON/GeoPackage files were written by `scripts/temporal_analysis.py`; editing them does not update the selected modern knowledge package.

The legacy runner is still present: it writes `data/runs`, and on success automatically copies audited polygons into `data/processed/<name>/sentinel2/<date>` using `promote_to_canonical`. Legacy `LandingZoneEngine` reads eligible runs with a processed-file fallback. This **does not change the modern knowledge registry**, but it is a separate older publication path and should not be confused with the main UI's pending-review workflow. The main application creates the legacy engine for compatibility routes as well as registering modern APIs.

## Practical implications

- A saved polygon GeoPackage in `processed` is an input/reference artifact; the registry identifies what the main version-bound application serves.
- A directory under `knowledge` can be active, pending, rejected, incomplete or a test artifact. Check registry, job decision and validation rather than assuming every directory is live.
- OSM/Overture reuse currently uses an AOI-and-date acquisition cache. Shared context reuse across dates is not implemented. Arbitrary files elsewhere are not discovered automatically.
- DEM reuse is independent of imagery date, with grid/coverage checks. Automatic local discovery recognizes the known FABDEM; other rasters can be explicitly registered/selected.
- These locations represent data lineage, derived products, caches and older implementations; similarly named files are not necessarily redundant. Any cleanup needs a dependency-aware manifest before moving or removing data.
