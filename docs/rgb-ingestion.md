# Dated RGB ingestion

Use **Build knowledge** to process a boundary and dated aerial image, inspect the finished candidate map, and select a dataset for use in **Application**. The app runs on Windows at the local address in the [setup guide](../README.md#start-on-windows).

## Prepare the inputs

| Input | Contract |
| --- | --- |
| Region name | Use a recognizable name and reuse it for later observations of the same region. The normalized name gives the region a stable `rgb-<slug>` identity in the registry. |
| Capture date | Supply the image's actual acquisition date in `YYYY-MM-DD` format, from the image catalog or flight log. Recognized GeoTIFF acquisition tags must agree. Use a date no later than today in India Standard Time and later than the currently accepted date for the RGB region. |
| Boundary | Supply valid polygon or multipolygon geometry in a GeoJSON file, up to **2 MiB**. Use RFC 7946 WGS 84 longitude and latitude. The region must lie within UTM coverage, span at most **8 km** in each projected dimension, cover at most **4 km²** and fit within **32 processing tiles**. |
| Imagery | Upload one internally georeferenced **8-bit RGB GeoTIFF**, up to **256 MiB**, with red, green and blue bands and optional alpha. A single image or same-date mosaic can cover the boundary. The image extent must contain the boundary. The worker also verifies valid pixels and opacity inside the boundary. |
| Working resolution | Use **0.5–2 m**. By default HELPS derives the projected native pixel size and bounds the working resolution to this range. Supply imagery with native detail of about **2 m** or finer. Finer imagery can be downsampled. Upsampling coarser imagery does not supply the required detail. |

Satellite or airborne sensors can supply RGB if the inputs meet this contract. A Sentinel-2 image at 10 m does not meet the detail requirement. Large, elongated or fragmented boundaries may hit the tile limit before the area limit. Crop to the portion covered by dated imagery and check that the full polygon fits.

## Model and worker setup

The app uses a SAM ViT-H checkpoint and the recovered GeoSAM composition and scene random forest. Bring these assets to the machine separately from the Git checkout. Set the following values in the checkout's ignored `.env` or the environment used to launch HELPS. Use absolute paths. Environment variables take precedence over `.env`.

| Setting | Required asset or runtime |
| --- | --- |
| `HELPS_RGB_SAM_REPO` | Meta Segment Anything checkout. The pilot used revision `dca509fe793f601edb92606367a655c15ac00fdf`. |
| `HELPS_RGB_SAM_CHECKPOINT` | Original `sam_vit_h_4b8939.pth`. The worker checks the file against its pinned SHA-256. |
| `HELPS_RGB_GEOSAM_REPO` | Recovered GeoSAM checkout containing `bhadra_highres_batches` and `samgeo_esri_test`. The local source audit pins revision `47843a288f195e1bbb1eb2df7481d7ec255c9eb1`. |
| `HELPS_RGB_FOREST` | Original `scene_random_forest.joblib`. The worker checks the file against its pinned SHA-256. |
| `HELPS_RGB_SAM_PYTHON` | Python executable for the SAM worker with the project geospatial dependencies and CPU PyTorch and torchvision. The pilot used Python 3.10, `torch 2.7.1+cpu` and `torchvision 0.22.1+cpu`. |
| `HELPS_RGB_CLASSIFIER_PYTHON` | Python executable with the project geospatial dependencies, scikit-image, scikit-learn **1.8.0** and joblib. The pilot used Python 3.12 and joblib 1.5.3. |
| `HELPS_RGB_TORCH_PACKAGES`, `HELPS_RGB_CLASSIFIER_PACKAGES` | Optional package directories for isolated dependency installs. When dependencies are installed in the worker environments, those interpreters can use empty package directories. |
| `HELPS_RGB_DEM` | Optional local elevation GeoTIFF in metres. A configured file must pass coverage checks for the boundary and slope calculation margin. With this setting unset, the worker tries a covering cached surface model, then public elevation. |

After the application setup, install the CPU model dependencies into the app's Python environment and create a separate Python 3.12 environment for the classifier. Run these commands in PowerShell from the repository root.

```powershell
.\.venv\Scripts\python.exe -m pip install --index-url https://download.pytorch.org/whl/cpu 'torch==2.7.1' 'torchvision==0.22.1'
$classifierEnv = Join-Path $env:LOCALAPPDATA 'HELPS\classifier-venv'
py -3.12 -m venv $classifierEnv
& (Join-Path $classifierEnv 'Scripts\python.exe') -m pip install -r requirements.txt scikit-image 'scikit-learn==1.8.0' 'joblib==1.5.3'
```

Point `HELPS_RGB_SAM_PYTHON` to the app's `.venv\Scripts\python.exe` and `HELPS_RGB_CLASSIFIER_PYTHON` to the classifier environment's `Scripts\python.exe`. Set the four model asset paths in the table before submitting a build.

The original forest is scene-specific. Use the matched GeoSAM code and model artifact together. Existing accepted packages can be viewed without loading these models. [Segment Anything source](https://github.com/facebookresearch/segment-anything) · [Recovered GeoSAM source](https://github.com/Nehareddy1234/cv_ai_helps).

## Track and review a build

Start the job in **Build knowledge**. One RGB worker runs at a time. The detached Windows process persists progress under `data/knowledge/rgb-jobs/` so that you can close the browser, stop Flask and later reopen the job list. Keep Windows awake while the build runs. If the job is interrupted or fails, inspect its reported error before resuming. A resumed job can reuse verified tile checkpoints from the original inputs.

The finished job is pending review. Open the preview to compare it with the current dataset and see the candidate area, geometry, slope and source completeness. Confirm the proposal to make it current for the region, or reject it. A rejected job retains its artifacts and the current selection. A valid run can finish with zero candidates.

### HTTP endpoints

The local API accepts a multipart submission. The optional `resolution_m` overrides the automatic working resolution. The example supplies **1 m** and assumes the source image has at least that level of detail.

```powershell
curl.exe -fS http://127.0.0.1:5000/api/knowledge/rgb/build `
  -H 'X-HELPS-Role: engineer' `
  -F 'name=Example region' `
  -F 'date=2026-10-01' `
  -F 'boundary=@C:/imagery/region.geojson' `
  -F 'image=@C:/imagery/region-rgb.tif' `
  -F 'resolution_m=1'
```

| Method and path | Use |
| --- | --- |
| `GET /api/knowledge/rgb/jobs` | List RGB jobs and their states. |
| `GET /api/knowledge/jobs/<job_id>` | Inspect a job and its current stage. |
| `POST /api/knowledge/rgb/jobs/<job_id>/resume` | Resume an interrupted or failed RGB build using its staged inputs. |
| `GET /api/knowledge/jobs/<job_id>/preview` | Read the review summary for a finished proposal. |
| `GET /api/knowledge/jobs/<job_id>/preview?format=geojson` | Load the proposed map and its preview token. |
| `POST /api/knowledge/jobs/<job_id>/accept` | Select the reviewed dataset. Send the preview token as JSON, `{"preview_token":"…"}`. Reload the preview if it has become stale. |
| `POST /api/knowledge/jobs/<job_id>/reject` | Reject the proposal and leave the current selection in place. |

## Processing and output

1. HELPS stages and validates the boundary, image and date, then plans overlapping image tiles. The worker verifies pixel coverage and reuses or acquires a covering elevation window, including the margin needed for slope.
2. SAM ViT-H proposes masks. GeoSAM composes them and the random forest assigns land-cover classes. Model processing has a **30-minute limit per tile**. The worker clips each tile to its core and to the requested boundary. It stitches class **3** (crop, grass and low vegetation) and class **4** (bare, open and sparse ground) as potential seeds.
3. The worker intersects the stitched seeds with valid **30 m** slope cells at or below **15°** and applies the shared minimums of **900 m²** area, **30 m** length and width, and **30 m** clear diameter. Aircraft-specific checks run separately in **Application**.
4. The shared knowledge builder writes a validated `knowledge.gpkg` and a manifest. The package contains candidate terrain, measured slope subregions, features, source records and lineage. The review workflow uses this same package, and acceptance records the selected version in `data/knowledge/registry.json`.

Each build's artifacts are in `data/knowledge/datasets/<dataset_id>/`. This directory contains the staged inputs, classified tiles and their checkpoints, `screening/`, `screening-audit.csv`, `candidate-seed.gpkg`, `rasters/`, `build.log`, `manifest.json` and `knowledge.gpkg` as stages complete. Check the persisted job error first for input validation, model setup, imagery coverage or elevation acquisition failures. A model runtime error can also point to a tile's segmentation log. Preserve the job files and package manifests to keep source provenance and resume checkpoints usable.

RGB classifications and 30 m elevation support research screening. Classes 3 and 4 can include ground unsuitable for a specific aircraft or mission. Public Copernicus GLO-30 models the surface, including some vegetation and structures. Ground firmness, obstacle height, approach clearance and authoritative restrictions need independent evidence. [Elevation provenance](automatic-elevation.md) · [Model audit](reviews/2026-10-20/cv-integration-assessment.md).
