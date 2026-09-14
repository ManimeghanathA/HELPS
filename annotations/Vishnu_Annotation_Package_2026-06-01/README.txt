HELPSs MANUAL LAND ANNOTATION PACKAGE
Observation date: 2026-06-01
CRS: EPSG:32643
Raster resolution: 10 metres

STARTING THE TASK

1. Install QGIS.
2. Open:
   Sample_01\Vishnu_Annotation_Sample_01.qgz
3. Keep sample_01_spectral visible.
4. Keep sample_01_scl switched off during normal visual annotation.
5. Do not use or view any automated model predictions.

LAYERS

sample_01_boundary:
The complete area that must be annotated.

open_land_annotations:
Draw polygons around visible open/empty land.
Set:
- annotation_id: OPEN_001, OPEN_002, etc.
- observation_date: 2026-06-01
- manual_class: open_land
- notes: optional

closed_land_annotations:
Draw polygons around clearly non-open regions.
Set manual_class to exactly one of:
- dense_vegetation
- water
- built_up
- cloud_shadow
- uncertain

Use annotation IDs such as:
- CLOSED_001
- CLOSED_002

ANNOTATION RULES

- Draw the actual visible boundary.
- Do not use rectangles around individual land regions.
- Do not overlap open and closed polygons.
- Do not annotate outside sample_01_boundary.
- Use uncertain when the class cannot be confidently identified.
- Save edits frequently.

SUBMISSION

First send:
1. The edited manual_annotations.gpkg
2. A full QGIS screenshot
3. A brief note describing uncertain regions

After review, export:
- open_land_annotations as open_land_annotations.geojson
- closed_land_annotations as closed_land_annotations.geojson