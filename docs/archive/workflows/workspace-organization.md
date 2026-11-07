# Canonical HELPS workspace

## 21 October 2026 handover update

The authoritative newcomer guide is now the root [README](../README.md). It covers the complete pipeline, original eight phases, version history, actual vision refinement, recommendation formula, temporal evidence and the remaining seasonal/vision integration problem.

The live selected Bhadra package is now `bhadra-cv-20260601-313234b7`: 4,474 candidates and 25,931 slope subregions. The earlier June/enrichment packages remain preserved; statements below about the selection refer to their historical cleanup dates.

The latest organization moved only loose, non-runtime material:

- Six team batch ZIPs → `data/raw/vision/batches/`.
- Root frontend change note → `docs/requests/frontend-changes-2026-10-17.txt`.
- Old AOI/polygon PNG export directories and their ZIPs → `data/archive/reference-exports/`.

Every moved file was hashed before/after and recorded in [workspace-moves-2026-10-21.json](workspace-moves-2026-10-21.json). No files were deleted. The pinned `probably_final.qgz/` GeoPackage, accepted knowledge packages, raw/processed routing, source manifests and environment were not relocated.

**Subsequent owner change, 21 October:** the owner moved the complete `probably_final.qgz/` directory into `data/probably_final.qgz/` so the Drive data upload includes it. The GeoPackage checksum was reverified. The refinement runner now prefers that location and supports the old root layout as a fallback. Immutable accepted-package provenance remains unchanged. The [Drive restoration guide](restore-from-drive.md) documents the sharing link, complete local layout, checksum verification and mutable path relocation for another computer.

New ignore rules keep downloaded/generated local data, source-review caches, vision inputs and runtime files out of new commits. Existing tracked reference assets remain tracked; TIFFs retain Git LFS. [data-assets-2026-10-21.json](data-assets-2026-10-21.json) records matching paths, sizes and checksums for the accepted build's key assets. A clone requires separate data transfer; a Git push is not a backup of ignored datasets.

Do not rerun the earlier one-time organizer to organize the current project. It predates newer knowledge/recommendation modules. The dated manifests document completed moves rather than a general cleanup command.

## Earlier consolidation

As of 2026-10-17, the runnable application, pipeline, tests and environment are in the single HELPSs project root. Start with `launch.ps1`; the ordinary interface has Overview, Map, Candidates, Application and Build knowledge tabs. There is no second draft checkout or role-specific application entry.

- `scripts/`, `templates/`, `static/`, `tests/`: current implementation.
- `data/raw/`, `data/processed/`, `data/knowledge/`: raw inputs, dated scans and validated linked knowledge. Temporal dates and immutable package versions are scientific history, not duplicate working folders.
- `docs/reports/`: original project reports and editorial notes.
- `docs/requests/`: the supplied change list and threshold notes.
- `docs/reviews/`: tests, review records and screenshots.
- `data/archive/recovery/2026-10-17-unified/`: both Git bundles, original source snapshots, final source recovery, original data conflicts, and a SHA-256 migration manifest. The selected knowledge GeoPackage is unchanged.

The existing `.env` remains local and ignored. One `.venv` is retained with its launchers relocated to this root. Generated test workspaces, duplicate environment and redundant draft files were removed after recovery and transfer checks. Historical observations and original user reports were retained.

Published package provenance retains the original acquisition paths as historical evidence. Mutable registry/source routing and the reusable build example point to the canonical root. Do not manually edit a published GeoPackage or its hash-bearing source manifest; build and validate a new dated package through the workspace instead.

## Earlier archive record


The cleanup on 2026-09-13 archived 115 items, relocated the OSM request cache to `data/cache/osmnx`, and deleted 12 superseded generated masks/overlays. Exact source and destination paths are listed in [cleanup-manifest.json](cleanup-manifest.json). Generated Python bytecode and empty former script directories were also removed.

## Active Data

- `data/raw/Bhadra/bhadra_entire_region.geojson` is the authoritative AOI.
- Original Sentinel tiles and four DEM sources remain in their raw folders.
- Bhadra spectral/SCL rasters, the current possible-open mask, final GeoPackage, final image, RGB preview and rejection map remain visible under the observation date.
- The complete OSM and Overture inputs remain visible. The historical prefiltered Overture input is retained in the buildings archive to explain the baseline's provenance.
- Manual annotations, validation rasters and sample geometry remain under `data/validation`.

## Archives

Historical code is in `scripts/archive`, retaining its original category structure. This includes the old hard-coded runners, OSM obstacle-removal experiment, live CDSE authentication utility, boundary construction, diagnostics and visual experiments. Archived scripts and old QGIS projects may require relinking historical paths before they can be used independently.

Within data folders, superseded boundary versions, intermediate vectors, diagnostics, auxiliary metadata, bounding-box building exports and the intermediate DEM are in sibling `archive` directories. Source imagery, annotations and final reference results were not deleted.

The duplicate packaged annotation directory and ZIP are preserved under `data/validation/archive`. Historical root-level QGIS projects, notes and screenshots are in the root `archive`. Research documents and papers are in `docs/archive`.

Only explicitly listed obsolete generated masks and overlays were deleted. They belonged to the superseded V1/OSM-raster workflow or duplicated newer final visualizations.

## New Runs

Each new run has a distinct directory with `run.json`, `run.log`, the AOI, final polygons, image and summary. Intermediate masks and stages are stored under its `archive`. Failed runs retain their logs and failure status; they do not become successful results.

Do not rerun `scripts/organize_workspace.ps1`: it is a one-time recorded migration and refuses to run when its manifest already exists. Git ignores local bulk data while retaining source archives and selected documentation figures.
