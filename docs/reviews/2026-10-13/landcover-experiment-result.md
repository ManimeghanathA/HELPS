# Full Bhadra land-cover experiment — 13 October 2026

The first full-AOI experiment is finished and available in the existing HELPS UI at http://127.0.0.1:8770. The baseline UI remains at http://127.0.0.1:8766. These are separate local servers. The experiment was not promoted to canonical data.

Output: `HELPS - draft/data/experiments/bhadra_20261013T115403_74d894/`.

## Result

| Metric | Stored Neha baseline | New experiment |
|---|---:|---:|
| Candidate count | 2,484 | 191 |
| Candidate area | 36.683 km² | 1.121 km² |
| Source imagery | June 1, 2026 | June 1, 2026 |
| Land-cover exclusion | None in this pipeline | WorldCover 2021 |
| Measured physical accuracy | Unmeasured | Unmeasured |

This reduction is not a count of verified false positives removed. Conservative screening will also reject some usable terrain. The live baseline contains 2,477 candidates after seven reported quarantines; the comparison table uses the intact stored baseline.

WorldCover acquisition succeeded and was aligned to all 21,293,562 pixels in the imagery rectangle. No coverage was missing. The source AOI contains 11,073,317 nonzero SCL pixels. Land-cover screening withheld 56,444 pixels that passed conservative spectral screening. It excludes tree/shrub cover, built-up areas, water, wetlands, mangroves and snow/ice, with a one-cell uncertainty buffer. Missing or unrecognised reference categories become UNKNOWN. Cropland and grassland are not universally excluded; the independent spectral gate still applies.

The run then subtracted 33,896 available building footprints with 10 m uncertainty margins, 36 legacy mapped water features with shoreline margins, and the seven reviewed exclusions. Area/shape and 30 m clearance gates reduced 367 parent candidates to 191 final zones.

Final audits passed: zero non-open, UNKNOWN and cloud overlap pixels, zero mutual overlap pairs, valid geometries, consistent stored areas and unique IDs. Building-buffer overlap was 1.37e-10 m² (below numerical tolerance); water and reviewed-exclusion overlap were zero.

All seven reported sites have zero overlap with final experiment geometry. In the six most recent reported sites, pre-quarantine open-pixel counts are 2, 16, 0, 1, 0 and 0 respectively for IDs 000020, 000056, 000095, 000211, 000283 and 000304. The tank-compound site 000874 still has 194 screened open pixel centres; its reviewed exclusion is still necessary. These known negatives are regression examples, not a held-out validation set.

## Verification

- 72 Python tests and 4 JavaScript/UI tests passed; Git diff whitespace checks passed.
- Browser verification selected Bhadra in the experimental UI and visibly displayed 191 candidate polygons with an experimental/incomplete-coverage banner.
- Screenshot: `experimental-ui-191.jpg`.
- Independent code review verified exact-grid checks, missing-data handling, buffering and publication guards. Its provenance finding was addressed in the reproducible runner and output metadata. The first run's reviewed registry snapshot was captured afterwards; the seven-feature registry was unchanged during this run and that capture timing is explicitly recorded.

A new test initially lacked isolation and briefly overwrote the draft canonical baseline. It was immediately restored byte-for-byte from the committed GeoPackage, verified as 2,484 polygons, and backed up to `bhadra-baseline-236c34c.gpkg`. The test now redirects publication to an isolated temporary root. The original workspace's separate datasets were not involved.

## Remaining blockers and limits

Industrial and facility source layers are still missing. The new bounded download attempt was not started because automatic approval review timed out, including its one permitted retry. Earlier attempts had provider HTTP errors/timeouts. The experiment declares these missing groups and cannot pass the complete-run publication guard. They were not replaced with fabricated empty evidence.

No local Earth Engine credentials file was found at the standard path, so newer Dynamic World acquisition was not established. WorldCover is historical (2021), not current obstacle ground truth. Both it and the current spectral inputs have roughly 10 m scale limitations and can miss individual trees or small structures. Existing water evidence lacks established linear-waterway and date completeness.

Next: obtain the missing exclusion sources and date-appropriate classification evidence, inspect a small separate sample against aligned reference imagery, then measure false positives and rejection of usable terrain. The 191 candidates remain unverified terrain proposals, not certified landing locations. Computed clear diameter describes the geometry of surviving evidence, not independently measured physical clearance. The existing UI ranking/slope heuristics are not validated by this experiment.
