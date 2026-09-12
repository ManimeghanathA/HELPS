# Workspace and Pipeline Plan

Goal: organize HELPSs and provide a local AOI/date application using the established single-date algorithms.

Architecture: reusable processing remains in scripts/processing. New scripts/pipeline modules own input validation, acquisition, orchestration and output audits. scripts/ui serves a local browser application using the Python standard library. Tests remain in tests.

Constraints: NDVI <= 0.50, MNDWI < 0, SCL uncertainty and three-pixel cloud buffer; 900 square metres, 30 metre length/width, 15 metre opening radius, 30 metre MIC diameter, 0.5 metre polylabel tolerance. DEM and roads remain context only.

1. Add tests for invalid AOIs, geometry/date cache keys, empty terrain/building subtraction, and synthetic end-to-end processing.
2. Implement AOI validation and content-addressed inputs, with explicit recognition of the existing Bhadra source data. Never identify an AOI by its display name alone.
3. Implement reusable Sentinel tiled requests and mosaicking, OSM context acquisition and Overture building acquisition. Record completed acquisitions; failed downloads cannot become cache hits.
4. Orchestrate existing processing functions. Save intermediates, polygons, image and JSON summary. Run unit tests before application runs and fail on final audit violations.
5. Build upload/date UI, progress log, previous results, image and downloads. Bind to loopback; restrict file serving to published run artifacts.
6. Archive historical scripts and superseded data locally with a move manifest. Preserve reference rasters, authoritative AOI, building inputs, validation annotations and the final Bhadra results. Delete only documented obsolete generated outputs.
7. Run unit/integration tests, reproduce Bhadra, inspect desktop/mobile UI and publish README figures. Start local server.

Data policy: each existing data directory has an archive subdirectory (excluding archives themselves). Only put superseded files there; do not relocate live dependencies. Source archives are tracked by Git; large local data and credentials are ignored. README figures are copied to docs/results for GitHub.
