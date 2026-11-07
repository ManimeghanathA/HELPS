# Raichur RGB prototype

In HELPS, open **Build knowledge** and select **Raichur · dated RGB prototype**. Upload a dated crop, then inspect and confirm the completed build to make it current in the map and Application. The September 2025 tile is already selected in this workspace as `raichur-rgb-20250901-6c329e7c`. The pilot button can bootstrap a fresh registry when the local tile is present. The existing Bhadra Sentinel form and its selected dataset are independent.

## Input contract

- One fully observed, north-up RGB GeoTIFF in EPSG:32643. Use 8-bit red, green and blue bands, with an optional fully opaque fourth band.
- Use square pixels from 0.5 to 2 m, 32 to 1,024 pixels per side, at most 512 m per side and at most 16 MiB. Crop and, if necessary, downsample finer imagery before upload. These are prototype limits.
- The raster footprint supplies the region boundary. The prototype accepts tiles inside a rectangular envelope around Raichur, 75.75–77.65° E and 15.65–16.75° N, rather than using the district's administrative boundary.
- Enter the local capture date from the source catalog or flight log. HELPS cross checks recognized image metadata and prior uploads of identical bytes. A new current observation must have a later date than the one already selected.
- SAM inference and classification share a 30 minute wall clock limit. A job may spend additional time in the queue or preparing elevation and knowledge.

## Processing and outputs

SAM ViT-H proposes masks and the recovered GeoSAM composition and original forest classify the regions. The producer contracts the predicted bare ground by 5 m and applies the existing minimum geometry and clearance rules before handing polygons to HELPS. The shared builder derives slope and roughness on its 30 m terrain grid, generates aircraft slope subregions and packages the features used by the existing recommendation engine.

The producer checks the local Copernicus GLO-30 window for coverage, including the derivative halo. When it cannot cover the tile, the existing elevation adapter obtains a covering public elevation window. Copernicus GLO-30 is a digital surface model. Its measurements can include vegetation and structures. Independent mapped obstacle, road, water and restriction coverage for the prototype is unknown. The package records that status, and the application applies its existing missing evidence policy. This is research screening and the pilot can legitimately return zero candidates.

The files are kept under `data/knowledge/datasets/<Raichur dataset ID>/`. Open `segmentation.gpkg` in QGIS for the class polygons and candidate seeds, `rasters/slope.tif` for slope, and `knowledge.gpkg` for the validated recommendation input. The folder also contains the input imagery, packed SAM masks, source records, model settings, timings and build logs.

## Local model setup

This checkout can use the assets restored for the earlier Raichur pilot. For a new machine or persistent installation, set the following paths in the local `.env` or environment. Use absolute paths.

| Setting | Value |
| --- | --- |
| `HELPS_RGB_SAM_REPO` | Meta Segment Anything checkout, pilot revision `dca509fe793f601edb92606367a655c15ac00fdf` |
| `HELPS_RGB_SAM_CHECKPOINT` | Original `sam_vit_h_4b8939.pth`, verified by SHA-256 |
| `HELPS_RGB_GEOSAM_REPO` | Neha's recovered repository, pilot revision `9e46fe31ea46f208dea0229d3bfd7eb394e3e510`, including `bhadra_highres_batches` and `samgeo_esri_test` |
| `HELPS_RGB_FOREST` | Original `scene_random_forest.joblib`, verified by SHA-256 |
| `HELPS_RGB_SAM_PYTHON` | SAM worker Python, defaults to the application Python. Install the project's geospatial dependencies plus CPU PyTorch and torchvision compatible with this interpreter. The pilot used Python 3.10, torch 2.7.1+cpu and torchvision 0.22.1+cpu. |
| `HELPS_RGB_CLASSIFIER_PYTHON` | Classifier worker Python. The pilot used Python 3.12 with the project geospatial dependencies, scikit-image, scikit-learn 1.8.0 and joblib 1.5.3. |
| `HELPS_RGB_TORCH_PACKAGES`, `HELPS_RGB_CLASSIFIER_PACKAGES` | Optional package directories for isolated installs. Python environments with their dependencies already installed can use an empty directory. |

[SAM repository](https://github.com/facebookresearch/segment-anything) · [Neha's repository](https://github.com/Nehareddy1234/cv_ai_helps) · [Raichur imagery catalog](https://api.imagery.hotosm.org/stac/collections/openaerialmap/items/69493f7684a859b011c94916)
