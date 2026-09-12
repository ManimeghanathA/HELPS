# HELPSs

Helicopter Emergency Landing Place Suggestion System: an explainable, terrain-first research pipeline for **possible open terrain**.

Select an AOI GeoJSON and a Sentinel observation date in the local application. HELPSs reuses verified local inputs or acquires missing Sentinel-2 L2A imagery, OSM context and Overture buildings, runs the established processing stages, and displays the candidate polygons over satellite imagery.

![Bhadra candidate polygons](docs/results/bhadra_final_open_land_zones.png)

## Current Results

The automated pipeline was rerun against the existing Bhadra inputs for **June 1, 2026**.

| Stage | Result |
|---|---:|
| AOI pixels | 11,073,317 |
| Possible-open pixels | 1,163,689 |
| UNKNOWN pixels inside observed AOI footprint | 1,154,896 |
| Open components | 19,697 |
| Geometry-qualified parents | 5,210 |
| Raw operational zones | 4,898 |
| Final candidate polygons | **4,130** |
| Final candidate area | **88.824 km²** |

The final audit passed: valid geometries, unique IDs, area/dimension/MIC thresholds, stored-area consistency, no positive zone overlaps, and no cloud or UNKNOWN pixel-centre overlaps. Building overlap is below the numerical tolerance of 0.000001 m². Machine-readable results are in [bhadra_summary.json](docs/results/bhadra_summary.json).

The new runner uses the complete AOI building inputs rather than the old prefiltered Overture export. The rerun produced 26,828 intermediate fragments versus the historical 26,827, with identical final polygon count and a total final-area difference of approximately 0.041 m². The original validated GeoPackage and figures are retained unchanged. This is a near-equivalent reproduction, not a claim of byte-identical geometry.

![Rejection reasons](docs/results/bhadra_rejection_reason_map.png)

## Run Locally

Python 3.10 is the verified environment. From the project root:

```powershell
python -m venv helps_env
.\helps_env\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m scripts.ui.server --port 8765
```

Open **http://127.0.0.1:8765**. Select a Polygon/MultiPolygon GeoJSON, enter its name and observation date, and run the analysis. The page shows progress, previous analyses, the final image, and PNG/GeoJSON/GeoPackage/JSON downloads. Use another port if 8765 is occupied.

For new Sentinel downloads, configure `.env` using the keys in `.env.example`:

```text
CDSE_CLIENT_ID=your_client_id
CDSE_CLIENT_SECRET=your_client_secret
```

Credentials stay local. Existing matching Bhadra data can run without new Sentinel authentication. OSM and Overture downloads need internet access; these are acquisition-time building/context snapshots, not historical snapshots for the Sentinel date.

The same workflow is available without the UI:

```powershell
python -m scripts.pipeline.run_aoi_pipeline --aoi data/raw/Bhadra/bhadra_entire_region.geojson --date 2026-06-01 --name Bhadra
```

Each run executes the active test suite before processing. Run the tests separately with:

```powershell
python -m pytest -q
```

## Processing

```text
Validate AOI and date -> verify cached inputs or download missing sources
-> prepare aligned 10 m Sentinel bands and SCL
-> possible-open detection with 30 m cloud buffer
-> polygonization -> exact building subtraction
-> geometry gate -> 15 m morphological opening
-> child geometry gate -> maximum-inscribed-circle gate
-> cloud/UNKNOWN and topology audits -> polygons, image and summary
```

The retained rules are NDVI <= 0.50, MNDWI < 0, observable SCL classes, explicit water exclusion, and UNKNOWN exclusion. The geometry gates are 900 m² minimum area, 30 m length and width, and 30 m maximum clear diameter with 0.5 m polylabel tolerance. Roads remain context; DEM/slope analysis is future work.

No usable observations produce a clear failure asking for another date. An observable AOI with no qualifying land produces a successful, empty polygon result. New downloads use a regional UTM grid; AOIs spanning more than six degrees or exceeding the local 40-million-pixel download limit are rejected.

## Project Layout

```text
scripts/
  pipeline/       Input validation, acquisition, orchestration and final audits
  processing/     Established terrain and geometry algorithms
  validation/     Reusable UNKNOWN overlap audit
  ui/             Local server, HTML, CSS and JavaScript
  archive/        Historical runners, diagnostics, boundary tools and old tests
tests/            Active offline unit and integration tests
docs/
  results/        GitHub-ready reference images and numerical results
  archive/        Historical research documents and papers
  cleanup-manifest.json
data/
  raw/            Authoritative AOI, original Sentinel tiles and DEM sources
  processed/      Retained Bhadra inputs and validated results
  inputs/         Geometry/date-keyed input manifests and downloaded data
  runs/           Independent run folders, final outputs and logs
  validation/     Manual annotations and validation packages
  archive/        Local historical data
archive/          Historical root-level notes, screenshots and QGIS projects
```

Each data directory has an `archive` subdirectory for superseded files. A run's diagnostic mask and intermediate vector layers live under its `archive`; final results remain at the run root. Matching geometry and date determine cache identity, not the user-entered name. Checksums detect changed inputs, and completion manifests prevent partial downloads from being treated as complete.

See [workspace organization](docs/workspace-organization.md) for archive details. Historical scripts are preserved as research history; their original hard-coded paths are not the supported entry point.

## GitHub Contents

Source code, archived source, tests, documentation, reference figures and the Bhadra AOI are prepared for Git. Large local rasters, downloaded vectors, run outputs, annotation packages, virtual environments, caches and `.env` are excluded. No repository or remote has been created, and nothing has been uploaded. Use external data storage or Git LFS separately if you decide to publish the large datasets.

## Verification and Scope

The local-data Bhadra pipeline has completed end to end. All 35 active tests pass, covering core algorithms, empty results, AOI/cache behavior, mocked Sentinel acquisition, and local HTTP access restrictions. The UI has been inspected at desktop and mobile sizes, including its AOI file chooser and completed-result downloads.

A separate live acquisition check on a small Bhadra-area polygon successfully downloaded Sentinel spectral/SCL rasters, queried all seven OSM groups, and completed the Overture query (zero buildings in that small test area). The initial sandboxed request was blocked; the live check succeeded with network access enabled. The full Bhadra run reused existing data. The small acquisition-check files are retained under `data/archive/acquisition_smoke`.

These outputs identify possible open terrain. They do not certify helicopter landing suitability: slope, surface strength, operational obstacles, permissions and helicopter-specific constraints are not yet evaluated. Residual thin-cloud contamination missed by single-date Sentinel SCL remains a documented limitation.
