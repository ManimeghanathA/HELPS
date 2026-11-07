# HELPS

**Helicopter Emergency Landing Place Suggestion System** turns dated aerial imagery into a reviewed terrain dataset and uses that dataset to rank research landing opportunities for LCH, LUH and ALH aircraft. **Build knowledge** prepares and reviews a region. **Application** assesses candidates against aircraft, mission, location and weather evidence.

HELPS is a local research tool. Its candidates require independent verification before any operational use.

## Start on Windows

From an existing checkout with Python and the local data in place, run `.\launch.ps1` in PowerShell and open [HELPS on localhost](http://127.0.0.1:5000). Use `.\launch.ps1 -Port 5001` to change the port.

For a fresh checkout, install Git, Git LFS and Python 3.10, then run these commands in PowerShell.

```powershell
git lfs install
git clone --branch codex/unified-helps https://github.com/ManimeghanathA/HELPS.git
Set-Location HELPS
git lfs pull
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path -LiteralPath .env)) { Copy-Item -LiteralPath .env.example -Destination .env }
.\.venv\Scripts\python.exe -m flask --app app run --host 127.0.0.1 --port 5000
```

To build from new imagery, configure the local SAM checkpoint, GeoSAM code, trained forest and worker environments. These assets are separate from the Flask dependencies. [Model and worker setup](docs/rgb-ingestion.md#model-and-worker-setup).

To open a previously accepted dataset on another computer, restore the matching local `data` tree and relink mutable paths using the Drive guide. Git contains the source and selected reference data. Generated knowledge, model weights, local credentials and bulk imagery are transferred separately. The guide records the original Bhadra backup and verification procedure. [Drive restoration](docs/restore-from-drive.md) · [Bhadra data manifest](docs/data-assets-2026-10-21.json).

## Build and approve terrain knowledge

1. Open **Build knowledge** and enter a region name and the image's capture date. Reuse the same region name for a later observation of that region.
2. Upload a polygon or multipolygon **GeoJSON** boundary and a georeferenced, dated **8-bit RGB GeoTIFF** that fully observes the boundary. An optional alpha band must be opaque within the boundary. Let HELPS derive the working resolution from the image or choose a resolution between **0.5 and 2 m**. The interactive build caps the area at **4 km²**, the plan at **32 tiles**, the image at **256 MiB** and the boundary at **2 MiB**. [Input contract](docs/rgb-ingestion.md#prepare-the-inputs).
3. Start the build and follow its status in the job list. The detached Windows worker tiles the image with overlap, uses SAM to propose regions and the GeoSAM random forest to classify them, and stitches class 3 and 4 seed geometry across tile boundaries. It reuses or acquires covering elevation, retains valid terrain at or below **15°**, applies the shared geometry and clearance rules, and builds a knowledge package for review.
4. Open the finished job's preview and inspect the map, candidate measurements and source limits. Confirm the proposal to select it for that region, or reject it. A pending or failed job leaves the previously selected dataset in use.

You can close the browser or stop Flask during processing and return to **Build knowledge** later. Keep Windows awake. Job status, resume behavior and review API calls are documented in the [RGB ingestion guide](docs/rgb-ingestion.md#track-and-review-a-build).

## Assess a landing opportunity

Choose a region with accepted knowledge in **Map** or **Application**. **Candidates** lists terrain footprints and measured slope subregions. In **Application**, choose an aircraft and mission, enter coordinates or select a point on the map, set the search radius, then run the assessment.

Open a result to see its footprint, score, evidence and checks that need verification. Known hard failures exclude a candidate. Research results can include candidates with unknown checks, and the engine can return zero opportunities. The score compares mission priorities using supported evidence and has no probabilistic interpretation. Candidate counts can change with coverage, imagery date, classification and terrain filters.

## Evidence and example results

The integrated RGB workflow continued after the Flask submitting process exited. On a 128 m × 128 m crop it produced two candidate terrain polygons and five threshold-specific slope subregions for review. The result demonstrates end-to-end processing on that crop. [Integration run and study boundary](docs/results/rgb-integration-2026-11-07.md).

The journal draft describes the workflow, the observed results and the validation still needed for accuracy and ranking claims. [IEEEtran manuscript](docs/paper/helps-ieee.tex) · [Two-column PDF](docs/paper/helps-ieee.pdf).

The RGB forest was developed on a different scene. Its labels can transfer imperfectly, particularly for crop cover and small obstacles. Public Copernicus GLO-30 elevation is a digital surface model at roughly 30 m and can include vegetation and structures. Neither input establishes ground firmness, complete obstacle or restriction coverage, or safe approach paths. [Elevation sources](docs/automatic-elevation.md) · [Vision model audit](docs/reviews/2026-10-20/cv-integration-assessment.md).

The restored **Bhadra** example `bhadra-cv-20260601-313234b7` is an accepted historical package with **4,474 terrain candidates** and **25,931 measured slope subregions**. Its Sentinel context is **2026-06-01** and its high-resolution vision imagery has an unknown acquisition date. The earlier **Raichur** pilot `raichur-rgb-20250901-6c329e7c` returned **zero** terrain candidates on its **2025-09-01** crop. These are results of earlier producers. The unified app builds new observations from dated RGB, and `data/knowledge/registry.json` records the selected packages in each local installation. [Bhadra delivery evidence](docs/reviews/2026-10-21-vision-refinement-delivery.md) · [Baseline recovery](docs/reviews/2026-10-18/neha-baseline-recovery.md).

## Repository and tests

| Location | Contents |
| --- | --- |
| `app.py`, `launch.ps1` | Local Flask entry points |
| `templates/`, `static/`, `scripts/ui/` | Browser interface and APIs |
| `scripts/knowledge/` | RGB processing, terrain measurement, package storage and review |
| `scripts/pipeline/`, `scripts/processing/` | Geospatial input, acquisition and geometry utilities |
| `scripts/recommendation/` | Aircraft checks, weather policy, ranking and explanations |
| `data/knowledge/` | Local registry, jobs and validated GeoPackages |
| `docs/reviews/`, `docs/archive/` | Dated reviews and historical material |

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
node --test tests/*.cjs tests/*.test.js
```

Node.js is needed for frontend tests. [RGB ingestion and API reference](docs/rgb-ingestion.md) · [Weather module](docs/reference/weather-module.md).
