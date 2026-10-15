# Saved Esri/SamGeo test checkpoint

This folder records the reviewed test from `HELPS/latest try` before adding the industrial structures requested on 2026-10-15. It includes scripts, input imagery, SAM masks, reviewed vectors, reports and QGIS projects. Large model weights and Python caches are deliberately excluded. GeoTIFFs use the repository's existing Git LFS rules; use `git lfs pull` after cloning.

The working folder remains `HELPS/latest try`; this is its Git checkpoint. The original QGIS projects and scripts reference sibling `samgeo` and `Codes` datasets and the local SAM checkpoint. They are an audit snapshot, not a standalone installation. The reviewed GeoPackage itself is portable: open `output/reviewed_test_classes.gpkg`, layer `reviewed_classes`, and apply `output/reviewed_test_classes.qml`. Its `buildings_reference` layer contains the accepted buildings clipped to the test footprint. Open `data/esri_test_aligned.tif` underneath to inspect the same Esri image without external project paths.

See `README_REVIEWED_TEST.md` for methods and limitations. This is a partially classified, visually reviewed test, not field-validated land-cover mapping or the complete Bhadra AOI.
