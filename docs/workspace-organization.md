# Workspace Organization

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
