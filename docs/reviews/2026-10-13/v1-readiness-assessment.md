# Full-original-scope V1 readiness assessment

The user rejected reducing V1 to the current interface prototype. All eight original phases are required. This assessment is read-only; product implementation under the new design has not started.

Working terrain: 2,477 retained candidates after the seven existing quarantines, 36.556781251 km². The source dataset remains 2,484 features. Preserve it as the parent layer; the 191-candidate experiment is not an adopted replacement.

## Verified terrain inputs

All four raw DEM tiles are valid, distinct arrays with complete retained-terrain extent coverage. EPSG:4326 grids are approximately 30 m, not independent 10 m evidence:

| File | Size/type | Validity and provenance |
|---|---|---|
| Copernicus_DSM_N13_E075.tif | 3601² float32 | All finite; metre units; edition/datum/source history incompletely documented |
| FABDEM_N13E075.tif | 3600² float32 | All valid; nodata -9999; metadata identifies FABDEM v1-2 and forest/building removal; CC BY-NC-SA 4.0 |
| N13E075.tif | 3601² int16 | All valid; nodata -32768; product edition/datum not established by filename |
| NASADEM_n13e075.tif | 3601² int16 | All valid; nodata -32768; metre units; remaining source metadata incomplete |

The existing prepared SRTM is 911×1480, EPSG:32643 at 30.5338 m, clipped to an older AOI. Only 29.5232% of retained polygon area intersects its valid-cell footprint. 459 retained polygons extend beyond its rectangle and 1,654 have zero valid coverage. Rebuild from a raw tile using a full-AOI halo and float32; do not reuse this prepared raster for slope.

OSM has 1,128 road features (1,127 lines), 28 buildings, 126 power features, four man-made polygons, 20 water MultiPolygons and four barriers. Overture has 33,867 valid building polygons. These support mapped proximity/density/context. Access tags and heights are incomplete, and mapped proximity does not establish road usability or flight clearance. Polygon repair/explosion explains differing prepared water/building feature counts.

The newer input-cache OSM package has only buildings, roads and an empty railways layer; missing water/industrial/facility groups remain incomplete. No authoritative restriction files were found. Debug restriction geometry is synthetic and must not become real coverage evidence.

## Verified software foundations and gaps

Full source geometry, holes, multipart handling, CRS conversion, quarantine, shared map/ranking geometry, source hashes, bounded acquisition and experimental publication guards are already implemented. Current draft verification last passed 72 Python and four JavaScript tests; that does not test the missing modules.

Missing original deliverables: terrain surface/vegetation/water/access characterization; real DEM slope/roughness; multi-threshold child operational zones; environmental context; normalized persistent hierarchy and spatial query contract; explicit dataset pinning; hard weather/aircraft/area/slope gates; exact footprint containment; context-driven missions; coherent processing/query UI; reproducible core/processing dependency specification and measured performance.

Current engine fabricates slope from clear diameter and assigns an unmeasured surface label. It awards missing weather favourable defaults and penalizes mandatory failures rather than consistently excluding them. Unknown profiles fall back silently. These are implementation defects, not future accuracy enhancements.

Global latest-completed-run selection can supersede the chosen broader Bhadra dataset. Replace it with an explicit AOI/date/dataset/version selection and an immutable loaded snapshot. Atomic GeoPackage copying alone does not activate all related evidence coherently.

## Implementation boundary

Original full SDD governs phase acceptance, not the older narrow AOI/date implementation milestone. The proposed design lives at `HELPS - draft/docs/superpowers/specs/2026-10-13-helps-v1-all-phases-design.md`. Broader obstacle/classification accuracy remains future scope by user choice, while invented measurements and missing required algorithms must be corrected for V1.

Available data support regional raster-derived terrain analysis. They cannot establish surface firmness, complete obstacle coverage, regulatory permission or footprint-scale physical accuracy. Missing external evidence must remain explicit and may block strict eligibility even when the software modules run.
