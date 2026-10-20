# Reported failures: evidence and next action

The user's twelve screenshots contain six readable source IDs. Source geometry areas and diameters match the screenshot values. These six were inspected against June 1 source imagery, NDVI, SCL and available building footprints. They are preserved as user-reported negatives, not independent validation labels.

| Source ID suffix | Old accepted pixel centres | Conservative retained centres | ESA WorldCover 2021 reference |
|---|---:|---:|---|
| 000020 | 207 | 2 | 201 cropland, 23 grassland |
| 000056 | 272 | 22 | 317 cropland, 13 trees |
| 000095 | 96 | 6 | 78 grassland, 29 built-up, 10 cropland |
| 000211 | 52 | 1 | 40 grassland, 18 cropland |
| 000283 | 116 | 0 | 110 trees, 28 grassland |
| 000304 | 36 | 8 | 29 trees, 4 built-up |

All 779 Sentinel source pixel centres are SCL class 5, and the old classifier accepts them all. The conservative profile retains 39 (5.0%). This is a pixel screening comparison; it is not a measured polygon accuracy improvement. WorldCover uses a different grid, so reference counts differ and must not be interpreted as square metres.

The six exact source geometries were appended to `HELPS - draft/data/raw/Bhadra/reviewed_exclusions.geojson`, with provenance and quarantine reasons. Baseline geometry was preserved. Reload was verified against the live API: all six IDs are absent and the live candidate count is 2,477. This includes the previous 000874 quarantine. Anonymous screenshot polygons were not guessed or selected by visual proximity.

## Recommended automated work

1. Add an explicit land-cover exclusion stage alongside source footprints: tree cover, built-up, water and wetlands, with uncertainty buffering and missing-data handling. The official WorldCover COG can be read without creating an account, and the diagnostic successfully read only windows covering the reported sites.
2. Combine this with the existing conservative spectral profile; tree-cover classification alone misses the cropland/grassland cases above. Crop surfaces are not automatically empty, and a tree plantation may be labelled cropland. Seasonal bare fields also must not be universally labelled obstructed solely because of a historical crop label.
3. Evaluate date-appropriate Dynamic World tree/built/water class probabilities if access can be configured. It is also derived from Sentinel imagery, so it supplies an additional classification model rather than finer spatial resolution or independent ground truth.
4. Preserve a separately labelled baseline and generate an explicit experimental screening result. Complete required obstacle acquisition and final geometry audits before promoting a new complete pipeline result. Do not silently turn missing facilities into empty evidence.
5. Use these reported sites as regression examples, then check a small automatically selected, separate sample for false positives and excessive rejection. Reusing known negative examples as the entire evaluation would not measure generalisation.

## Source limits

WorldCover v200 is a 2021 land-cover map, whereas candidate imagery is dated 2026-06-01. Old mapped obstacles can justify caution; old absence of obstacles cannot establish current clearance. WorldCover is approximately 10 m and does not resolve every individual tree or small building. Current imagery registration/date checks remain necessary for screenshots without identifiable IDs.

Official sources:

- https://esa-worldcover.org/en/data-access
- https://developers.google.com/earth-engine/datasets/catalog/ESA_WorldCover_v200
- https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_DYNAMICWORLD_V1

Machine-readable evidence: `reported-failures-batch.json` and `worldcover-reported-sites-evidence.json`. The reproducible reference diagnostic is `check_worldcover_reported_sites.py`. No new automated tree-cover exclusion stage or full Bhadra regeneration has been deployed in this milestone; live changes are the six reviewed quarantines.
