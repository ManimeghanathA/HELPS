# Reported industrial-looking candidate: Bhadra_ZONE_000874

The user supplied a Leaflet/Esri screenshot showing a candidate over circular tank-like structures and a developed yard. Inspection of the stored polygon and its June 1 Sentinel inputs confirms that the current rules accept this footprint as possible-open terrain before map rendering. The physical identity/date of each structure still requires reference verification.

## Measured evidence

- Polygon area: 50,552.885 m²; maximum inscribed-circle diameter: 140.561 m.
- Approximate polygon centroid: latitude 13.701294, longitude 75.641590. This is a reference for locating the polygon, not an operational landing coordinate.
- All 514 pixel centres within the polygon have SCL=5.
- All 514 are accepted by the updated per-class open-pixel classifier.
- NDVI ranges from -0.02991 to 0.49973; median 0.19587.
- 253 of those 514 pixels have NDVI > 0.20. They still pass because SCL=5 uses the 0.50 ceiling; the 0.20 ceiling applies only to SCL=4.
- No OSM buildings exist in the checked 100 m neighbourhood of this polygon in the committed source file.
- 76 Overture building footprints intersect its 100 m neighbourhood, but none has positive area intersecting this polygon.
- The committed OSM package has no `industrial` layer. The original calibrated run's complete exclusion package is not available, so its facility-mask coverage cannot be independently reconstructed.

## What this establishes

The classifier confuses a low-vegetation, spectrally dry-looking surface with empty ground when the available vectors do not mark its obstacles/facility. SCL=5 is not a guarantee of unobstructed ground. A mathematically clear circle is clear of the polygon boundaries and mapped exclusions; it is not proof of clearance from omitted real objects.

The existing code rounds and smooths the original raster-derived geometry through polygonization and morphological operations. Rounded stair-step outlines are expected consequences of the grid and buffering; their visual appearance alone does not determine physical suitability.

The earlier coordinate/geometry round-trip verification demonstrated that exported geometry matches stored geometry. That does not establish absolute positional accuracy of source imagery or date agreement with the Esri basemap. This case still needs stable-feature alignment and imagery-date checks; shifting the polygon without that evidence would be unjustified.

## How to distinguish error classes

1. **Display/export error:** compare UI GeoJSON with stored GIS geometry; preserve rings, CRS and multipart features. This path was corrected in the preceding milestone.
2. **Registration error:** compare several stable road junctions/building corners across source imagery and an independent georeferenced reference; measure consistent spatial residuals. Internal CRS matching alone does not supply ground truth.
3. **Date difference:** record source acquisition dates for both imagery layers and obstacle snapshots. Esri World Imagery may change source/date with location and zoom level.
4. **Detection/coverage error:** where observations agree in position/time but known obstacles remain inside a candidate, inspect SCL/indices and missing obstacle/facility masks. This candidate already demonstrates acceptance and an obstacle-coverage gap in the supplied inputs.

## Validation implications

Manual annotation is not obsolete. It should be performed only against documented, aligned reference imagery, with uncertain or temporally changed examples marked explicitly. Separate region geometry from labels. Start with this reported failure and additional roof/water/tree/industrial examples, then use a spatial holdout to evaluate fixes. Satellite appearance is useful validation evidence but does not establish surface strength or operational safety.

The appropriate next product step is an inspection view for a selected polygon: source Sentinel RGB, Esri reference/date metadata, classifier pixels, obstacle/facility layers, coordinates and evidence. It should precede another blanket threshold change. Acquisition should include appropriate facility tags and broader independent evidence rather than relying exclusively on building footprints and `landuse=industrial`.

No candidate dataset, detector threshold or production UI was changed during this investigation. Read-only diagnostic script: `inspect_zone.py`; evidence: `Bhadra_ZONE_000874-evidence.json`; comparison: `Bhadra_ZONE_000874-source-comparison.png`.

## Sources

- https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Data/S2L2A.html
- https://support.esri.com/en-us/knowledge-base/faq-can-the-date-of-an-image-be-determined-from-the-wor-000012181
