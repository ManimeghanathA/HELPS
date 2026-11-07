# Dated aerial imagery and terrain screening for potential helicopter landing areas in Raichur

## Abstract

We implemented a geospatial workflow that converts a dated RGB aerial image and public elevation data into a reviewable map of potential helicopter landing areas. Automatic masks from SAM ViT-H are composed into regions, classified from RGB and texture, and screened for opening geometry before terrain slope and aircraft-specific constraints are applied. In a 512 m × 512 m Raichur drone image at 0.5 m resolution, CPU inference produced 250 masks in 142.88 s, and subsequent classification produced 603 regions. The geometry stage retained zero candidate polygons. The system generated slope across the full tile at 30 m resolution and returned an empty shortlist. We describe the workflow and propose a controlled evaluation of how input resolution affects detection and shortlisting.

## Introduction

Landing area screening requires evidence about the surface, its usable extent and surrounding obstacles. Scherer et al. studied autonomous site selection with onboard lidar. We study an earlier planning task using dated aerial imagery and a public surface model. The output is a set of terrain candidates for human review. [Scherer et al., 2012](https://publications.ri.cmu.edu/storage/publications/pub_files/2012/9/1-s2.0-S0921889012001509-main.pdf)

The research question is how much spatial detail is needed to retain observable openings while excluding visible obstacles. A controlled comparison uses resampled versions of the same source image so that geography and observation date remain fixed.

## Data and methods

The feasibility tile comes from the WELL Labs Raichur drone orthomosaic captured on 1 September 2025 local time. We cropped a fully observed rectangle and used a 0.5 m RGB grid in EPSG:32643. Elevation derives from Copernicus GLO-30. RGB acquisition time and the elevation product's reference information are recorded separately. [Imagery catalog](https://api.imagery.hotosm.org/stac/collections/openaerialmap/items/69493f7684a859b011c94916) · [Copernicus elevation data](https://registry.opendata.aws/copernicus-dem/)

SAM ViT-H creates mask proposals. Region composition resolves mask overlaps and fills gaps using image edges. The original GeoSAM random forest estimates land cover from colour and texture, and region voting preserves uncertain predictions as a separate class. Candidate geometry starts from predicted bare ground, uses an inward buffer and passes through minimum area, width, length and clearance checks. The HELPS terrain module calculates slope and roughness from the elevation grid, produces connected slope subregions and supplies their attributes to the existing recommendation engine. [Kirillov et al., 2023](https://openaccess.thecvf.com/content/ICCV2023/html/Kirillov_Segment_Anything_ICCV_2023_paper.html)

## Feasibility evidence

The integrated build generated 250 automatic masks and composed 603 regions. CPU inference took 142.88 s with six PyTorch threads. Model loading took 26.71 s and the composition and classification stage took 31.46 s. The forest labelled 6,646.75 m² as possible bare ground and 58.12% of the classified area as uncertain. No candidate seed passed geometry and clearance screening. The prepared elevation and slope rasters covered the full tile, and the application returned zero eligible results. This run exercised the empty shortlist path. Evaluating ranking requires independently labelled tiles with candidates that pass the screening gates.

The integrated run is archived locally as `raichur-rgb-20250901-6c329e7c`. The segmentation summary records timing and model provenance, the GeoPackage contains the classes, and the build manifest records terrain coverage and validation.

## Evaluation protocol

1. Delineate visible openings and obstacle footprints on several held-out tiles from the source orthomosaic. Keep adjudicated labels separate from model tuning and mark visually ambiguous areas.
2. Resample each tile to 0.5, 1 and 2 m. Hold the geographic footprint, elevation raster, forest, candidate geometry rules, aircraft and weather policy constant. Record the effect of pixel scale on the texture and segmentation stages.
3. Report opening precision and recall, obstacle overlap, eligible candidate counts, rank overlap where rankings exist, and wall clock time per stage. Include the number of empty shortlists and confidence intervals across tiles. Use only date-matched imagery if adding an actual Sentinel baseline.
4. Describe cases where apparent openings are rejected by terrain or geometry, and cases where coarse elevation or unavailable obstacle evidence limits interpretation. Show representative successes and failures.

## Limitations

The elevation grid is coarser than the imagery and represents a surface model. The pilot has no independently verified obstacle inventory or ground survey. The classifier was developed on a different image source and geography. The application currently accepts one small crop at a time, and the measured CPU runtime is specific to the hardware and pilot input.
