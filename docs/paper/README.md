# HELPS research manuscript

- **Review PDF** — [helps-ieee.pdf](helps-ieee.pdf), a two-column copy rendered from the manuscript with ReportLab because this workspace has no LaTeX engine.
- **Editable journal source** — [helps-ieee.tex](helps-ieee.tex) uses the IEEEtran journal class. With a TeX distribution containing IEEEtran, run the command below from this folder. The reference list is embedded in the source.
- **Figures** — [workflow](figures/workflow.png), [Raichur classification](figures/raichur-pilot.png), and [Raichur terrain screening](figures/raichur-screening.png). The two maps use local geospatial evidence. The captions credit WELL Labs, the Open Imagery Network, OpenAerialMap, and Copernicus DEM.

    latexmk -pdf -interaction=nonstopmode -halt-on-error helps-ieee.tex

The manuscript uses a draft byline pending confirmation of authors and affiliations. Apply the target journal's requirements when preparing a submission.

## Evidence and figure reproduction

Run the following from the checkout root with the project environment. The generator uses the already archived raster and GIS layers and writes all three PNGs.

    .venv/Scripts/python.exe docs/paper/generate_figures.py

The figures in this folder are ready to use. Recreating them requires the local files below. The prototype job files under .tmp may need to be restored from the originating workspace.

| Evidence | Location in the checkout |
| --- | --- |
| 512 m orthomosaic and fixed-segment recovered-forest result | data/experiments/raichur-geosam-pilot-2026-11-07/rgb_050m.tif and neha-original/raichur_results.gpkg |
| Recovered-forest totals and verification | data/experiments/raichur-geosam-pilot-2026-11-07/neha-original/results.json, verification.json, and screening_decisions.csv |
| Separate 512 m integrated legacy build and timings | data/knowledge/datasets/raichur-rgb-20250901-6c329e7c/segmentation.json and manifest.json |
| 128 m prototype boundary, plan, tile outputs, slope, and screening audit | .tmp/raichur-district-worker-smoke/aoi.geojson and the adjacent job/ folder |
| 128 m unified upload-to-review result | data/knowledge/datasets/rgb-rgb-workflow-validation-20250901-6ee09498/manifest.json, screening-audit.csv, and knowledge.gpkg |
| Historical Bhadra delivery | docs/reviews/2026-10-21-vision-refinement-delivery.md |

The 512 m Raichur working-image SHA-256 is 71f6630dcf57ea859ba2d3e02c7771223bc2f905be783564d81e3b130140999c. The original Bhadra forest SHA-256 is 6b20051872b1722fd09ff30b4ac9000eeffab3d61269cc3ffcebcb6a4b5239f8. The SAM ViT-H checkpoint SHA-256 is a7bf3b02f3ebf1267aba913ff637d9a2d5c33d3173bb679e46d9f338c26f262e.

The archived Raichur imagery catalog identifies the local capture date and source item. OpenAerialMap's published CC BY 4.0 terms and the local capture record supply the attribution. Copernicus DEM attribution and terms appear in the manuscript. The historical Bhadra section reports package counts without redistributing its basemap imagery.
