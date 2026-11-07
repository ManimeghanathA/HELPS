# Bhadra segmentation research manuscript

- [Review PDF](helps-ieee.pdf) uses a two-column ReportLab layout because the workspace lacks a LaTeX engine.
- [Editable journal source](helps-ieee.tex) uses the IEEEtran journal class with numbered references. From this directory, run the command below with a TeX distribution containing IEEEtran.
- [Predicted classes and qualified footprints](figures/bhadra-segmentation.png) shows the same local window before and after overlaying the screening output.
- [Locations and slope distribution](figures/bhadra-additions.png) covers all 2,810 segmentation-derived additions.

    latexmk -pdf -interaction=nonstopmode -halt-on-error helps-ieee.tex

The byline is a draft pending confirmation of authors and affiliations.

## Reproduce the figures

Run the generator from the checkout root with the project environment. The generator reads the saved vector layers and writes the two thematic PNGs. The figures contain no basemap tiles.

    .venv/Scripts/python.exe docs/paper/generate_figures.py

The classified vectors and audited seed geometries are retained as local GIS artifacts. Restore the corresponding data folders before rerunning the generator.

| Evidence | Location in the checkout |
| --- | --- |
| Original classified polygons and Bhadra study boundary | data/probably_final.qgz/probably_final.gpkg, layers open_regions, other_regions, bhadra_boundary |
| Qualified footprint vectors with lineage | data/knowledge/bhadra-cv-20260601-313234b7/refinement-input/candidate_seed.gpkg, layers candidate_seed and vision_extent |
| Source decisions and screening parameters | data/knowledge/bhadra-cv-20260601-313234b7/refinement-input/geometry-decisions.jsonl and refinement-audit.json |
| Selected knowledge package, terrain rasters, and full audit | data/knowledge/bhadra-cv-20260601-313234b7/knowledge.gpkg, preparation-terrain/, and delivery-validation.json |
| Classification inventory and independent software checks | docs/reviews/2026-10-20/cv-final-geopackage-findings.md and docs/reviews/2026-10-21/vision-independent-validation.json |

The original classification GeoPackage SHA-256 is 575b980a4225eda768fd83fee29fbee2ae073bc8a578b8b256fb50290c14f634. The selected knowledge GeoPackage SHA-256 is 6f90f657eaec54a1c901b93907bd2a8f0e556264f6b976324a130c89ebbe883b. Figures and statistics select only rows with refinement_origin equal to vision_addition. The study used no independent ground truth for assessing classifications or candidate suitability.
