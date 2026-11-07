# Bhadra segmentation results

HELPS uses Bhadra, Karnataka as its documented case study. The selected package is `bhadra-cv-20260601-313234b7`. Its actual study boundary measures **1,107.33 km²** in EPSG:32643 and is the area used for this analysis.

## Segmentation-derived candidates

The analysis selects features marked `vision_addition` in the delivered GeoPackage. The producer screened 112,283 source regions classified as low vegetation or bare and sparse ground. It contracted each opening inward by 5 m, removed mapped obstacles and overlapping existing candidates, then applied the geometry and clearance gates. This Bhadra run required fully supported 30 m FABDEM slope at or below 12°.

| Source class | Candidates | Area |
| --- | ---: | ---: |
| Crops, grass and low vegetation | 1,508 | 5.336 km² |
| Bare soil, rock and sparse ground | 1,302 | 6.208 km² |
| Total | **2,810** | **11.543 km²** |

These polygons came from **2,569 distinct source segments**. The maximum measured slope admitted was **11.971°**. The package stores **17,540 slope subregions** linked to the 2,810 candidates across its degree thresholds. The same candidate can appear at several thresholds.

The application package contains **4,474 terrain candidates** and **25,931 slope subregions** across all origins. Those totals include other retained and refined features. The paper analyzes the segmentation-derived component and uses its lineage tags to keep that scope explicit.

## Evidence and limitations

The RGB acquisition date is unknown. The date attached to the stored package is a context date. The class labels and candidate footprints lack independent ground truth, so the counts cannot establish classification accuracy, hazard detection performance, or landing suitability. The separate current RGB uploader requires an acquisition date and applies a 15° prototype screening ceiling.

The totals and class breakdown were recomputed from the selected GeoPackage, whose SQLite quick check passed. The delivered audit separately checked source containment after contraction, terrain coverage, geometry and overlap. [Delivery audit](../reviews/2026-10-21-vision-refinement-delivery.md) · [Local data restoration](../restore-from-drive.md) · [Paper and figures](../paper/README.md)
