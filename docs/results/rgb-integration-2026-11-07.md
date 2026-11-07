# RGB workflow integration run

On 7 November 2026, the HELPS upload endpoint accepted a 128 m × 128 m boundary and dated 0.5 m RGB imagery. The Flask process that submitted the job exited. The detached worker continued through segmentation, terrain screening and knowledge package creation. A fresh Flask instance listed the completed job and returned the candidate map and preview token. The result was left pending review.

| Item | Recorded value |
| --- | --- |
| Dataset | `rgb-rgb-workflow-validation-20250901-6ee09498` |
| RGB capture date | 1 September 2025 local time |
| Study grid | EPSG:32643, 0.5 m, 128 m × 128 m |
| Processing tiles | 1 |
| SAM masks and composed regions before clipping | 93 masks, 132 regions |
| SAM CPU inference | 135.90 s, six threads, excluding model load |
| GeoSAM composition and classification | 5.38 s |
| Elevation | Copernicus GLO-30 DSM, verified full coverage of the study area and calculation margin |
| Candidate terrain | 2 polygons, combined area 3,863.75 m² |
| Connected slope subregions | 5 threshold-specific regions, including 2 at 15° |
| Review | Pending, with both candidate polygons visible in the preview response |

The study used the same imagery and footprint as the earlier 128 m screening experiment. The integration run verifies the workflow and is not an independent accuracy sample. A 30 m surface model cannot establish subpixel terrain roughness, ground firmness or complete obstacle clearance. Counts are candidate terrain and slope subregions, not operational recommendations.

[Study boundary](rgb-integration-aoi.geojson) · [Original imagery and CC BY 4.0 attribution](https://api.imagery.hotosm.org/stac/collections/openaerialmap/items/69493f7684a859b011c94916)
