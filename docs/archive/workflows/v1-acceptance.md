# HELPS V1 acceptance and evidence

Status correction (2026-10-14): the terrain/package/recommendation core is implemented locally and Bhadra is built, validated and activated. The original monthly imagery selection and temporal evidence workflow were not integrated into this V1 release; that missing scope is being implemented in the approved workflow revision. This is research decision support. Physical polygon accuracy and operational clearance are not certified.

The retained map contains **2,477 parent terrains**, from 2,484 source polygons and seven reviewed quarantines, covering **36.556781 km²**. The 191-candidate experiment is not adopted. The package adds **13,150 operational children**; threshold counts are 0°:0, 2°:1,057, 4°:1,633, 6°:1,843, 8°:1,981, 10°:2,097, 12°:2,218, 15°:2,321. Children at different thresholds may overlap by design. Every parent remains browseable independently of eligibility.

## Feature inventory

| Entity | Stored features |
|---|---|
| Parent identity and geometry | Dataset/terrain/source IDs, full rings and parts, original geometry hash, area, rotated width/length, bounds, interior reference coordinates, approximate maximum-inscribed-circle centre/radius/diameter |
| Parent surface observations | Separately dated Sentinel/SCL and historical WorldCover class proportions; raw, observable and unknown coverage; vegetation/bare/water indicators; raw and ground-observable NDVI; sample counts and source identities; unknown firmness |
| Measured terrain | Elevation and slope min/mean/max/std, detrended-plane RMS roughness min/mean/max/std, valid fractions and sample counts, native-scale 30 m grid, DEM identity/license and unresolved vertical datum |
| Parent access | Mapped road/water proximity, available road/access/highway/surface tags and coverage/provenance, including parents with no child |
| Operational child | Parent/source/dataset links, slope threshold, full clipped geometry, dimensions/area, exact full-boundary clearance at the computed centre, measured child slope/elevation/roughness, support, rejection/threshold lineage |
| Child environment | Declared 200 m context; mapped road/water/infrastructure/settlement/hospital distances when supplied; mapped graph components separate from traversability; union-counted mapped occupancy, 2D openness and coverage; dated surrounding vegetation/cover; water/restriction intersections and support; explicit unknown height/approach evidence |
| Package | AOI/date/version, hashes/CRS/units/coverage/source metadata, parameters, code/runtime fingerprint, stage logs/checkpoint hashes/timings, normalized source/entity relationships, foreign keys and spatial indexes, explicit selected-version registry |

Cloud/shadow/nodata class observations remain stored, but are not treated as observable ground. Partial spectral coverage and unknown obstacle coverage cannot earn favourable absence-based ranking factors. No firmness, tree height, vehicle accessibility, legal permission or favourable weather is invented.

## Recommendation contract

Independent pass/fail/unknown gates check weather, slope/support, area, diameter, exact circular footprint including holes/parts, surface compatibility and restrictions. A score cannot compensate for a failed or unknown mandatory gate. Strict eligible results can be empty with current external evidence; the separate bounded, deduplicated exploratory list remains inspectable and has no suitability score.

Balanced research weights use all eleven factors: distance .18, clearance .18, weather .12, area .07, slope .10, roughness .07, spectral bare-surface indicator .07, vegetation indicator .04, mapped road proximity .07, supported 2D openness .06 and mapped water distance .04. Other missions retain their declared priorities. Responses record factors, contributions, weights, missing/unused factors, scope/dates/support and straight-line ETA assumptions. Missing supported optional factors are omitted and remaining weights renormalized. Surface/vegetation scoring requires complete observable SCL coverage apart from a declared 1e-6 numerical tolerance. These weights require calibration; scores are relative priorities, not safety probabilities.

## Original phases

| Phase | Implementation and evidence |
|---|---|
| 1 Infrastructure | Validated imports and bounded acquisition, complete-context acquisition mode, full-area metric DEM; hash/grid/unit/coverage tests and real derivative support 1.0 |
| 2 Candidates | Retained import/quarantines and explicit new-candidate generation without canonical promotion; full geometry and synthetic pipeline tests |
| 3 Characterization | Area-weighted raster/geometry/context features; tiny/no-centre, nodata, unsigned negative NDVI, cloud and multi-parent regressions |
| 4 Operational zones | Horn slope, plane-RMS roughness, four-connected eight-threshold children and known exclusions; analytic planes, nesting/split/holes/water buffers/MIC checks |
| 5 Knowledge | Immutable normalized GeoPackage, actual foreign keys/RTree, explicit hash-validated activation; GIS readback, integrity, spatial-query equivalence and recovery tests |
| 6 Recommendations | Validated profiles/weather, indexed snapshots, mandatory gates, footprint, mission ranking/dedup/reasons; controlled weather and actual synthetic-package/build tests; real Open-Meteo lookup succeeded |
| 7 UI | Both roles, India-to-region navigation, recommendation/table/map selection, measured slope shades, managed sources/jobs/publication/export; API and JavaScript regressions; populated browser acceptance below |
| 8 Optimization/release | Offline reuse and code/runtime/source fingerprints, indexed queries/weather cache, exact prepared-cell sampling, isolated launcher; measured timings and final suites below |

## Build and review record

The final full run computed parent features in 100.28 s, slope children in 103.50 s, surrounding context in 170.96 s and package publication/audit in 67.32 s. The exact-cell optimization reduced parent characterization from 455.93 s and context from 752.82 s without dropping features or boundary/hole intersections. Full stage manifests retain timings and provenance.

Initial clean environment: system packages disabled and no review-only imports; 183 Python tests passed in 21.79 s and 15 Node tests passed. Final isolated release suite: **192 Python tests passed in 24.75 s; 17 JavaScript tests passed**. Independent whole-architecture review found three issues in observability/openness/context acquisition; scoped re-review confirms all addressed with no new important regression, 36 focused tests passed.

## External evidence limits and future work

Mapped obstacle completeness and current physical polygon accuracy remain unmeasured. Sentinel pixels cannot resolve every building/tree; historical WorldCover and satellite basemap dates are separate evidence. Firmness, obstacle heights, aviation permission and road traversability remain unverified. The original 4,130-reference temporal database is not joined by ID to these parents. Higher-resolution obstacle/canopy evidence, independent accuracy evaluation and operational validation remain future work.

FABDEM v1-2 carries CC BY-NC-SA 4.0, Bristol/Fathom attribution; WorldCover 2021 v200 carries recorded CC BY 4.0. Source/output distribution rights are separate from code licensing. Recovery retains previous immutable packages and explicitly activates a registered version; no latest-folder selection is used.

## Final local acceptance

The authoritative package is `data/knowledge/bhadra-v1-20260601-fabdem-20261013/knowledge.gpkg`, 201,728,000 bytes, SHA-256 `0ded087336e671d5e7c1f2cb12ab84a62c94077055aff979ed79dfa86d02ebd9`. Package validation succeeds, SQLite integrity is `ok`, foreign-key violations are empty, and Bhadra explicitly selects this version. The download API returns HTTP 200, the exact package byte count and versioned attachment name; an invalid engineering build preserves this selected version.

Browser walkthrough verified both roles, published-region/version selection, the 25-row feature table, candidate-to-map navigation, native-scale slope shading and all threshold choices. At 0° the child count is zero and parents remain available; at 6° the child count is 1,843. Source registration displays actual CRS, counts, bounds, tags, hashes and missing coverage. A deliberate invalid DEM job fails with `DEM vertical units must be declared metres or feet` and an explicit published-data-preserved status. The 390×844 responsive view has no document horizontal overflow. Long child IDs wrap in the evidence panel. Actual provider assessments produce a separate bounded exploratory list, complete gate explanations, full selected geometry, reference marker and footprint circle.

Real-data acceptance caught fully supported DEM fractions differing from 1 by at most 3.34e-13. The recommendation gate now declares a fixed 1e-12 arithmetic-only coverage tolerance, preserves raw values, and does not change slope or footprint limits. Actual-value, larger-deficit and partial-coverage regressions passed; independent scoped review found no issues. Submission waits for region loading to finish, avoiding invalidated assessment responses.

Measured cold repository initialization: 26.53 s; listing parents: 1.69 s; 20 km indexed query (10,138 children): 9.98 s; controlled full assessment: 24.31 s. Initial UI requests can take longer because validation runs on first access. These measurements are local, not a throughput guarantee. The full feature inventory is preserved. Final review details, execution choices and tradeoffs are in `docs/v1-delivery-decisions.md`.

Evidence is saved under `docs/reviews/2026-10-13/`: source validation, integrity/activation, controlled recommendation, live-provider lookup, timing, export checks, engineering-validation and responsive/map screenshots. Existing physical polygon false positives remain an external evidence limitation; completion of the software workflow does not establish measured detection accuracy.
