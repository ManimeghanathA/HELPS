# Knowledge workflow delivery — 17–18 October 2026

## Implemented behaviour

- Processing never selects a dataset. Completed packages persist as pending review, with complete parent polygons, candidate/slope-zone counts, area/date, selected-feature evidence, source limitations and current-versus-proposed comparison.
- Confirm replacement uses one guarded accept endpoint. A preview token binds the inspected package checksum and current dataset identity; changed packages and stale-current reviews fail. Rejection is durable and preserves artifacts/current knowledge. Rejected/unpublished packages cannot enter recommendation or managed-history selection.
- Legacy publication cannot bypass the review gate. Acceptance is registry-serialized; decision persistence failure rolls back publication/selection. Persisted jobs survive restart; interrupted jobs are reported failed and can never activate themselves.
- Same-date enrichment is a separate operation: source checksum, date and exact geometry/measurements/lineage must remain preserved. Normal scans remain strictly forward-dated. Opening the saved June 1 package reproduces its exact polygons; running changed detection code against June 1 imagery is not promised to reproduce that seed.
- Temporal ranking is soft only. Every mission reserves heuristic weight 0.10; previous factor ratios retain 0.90. Effective temporal weight is configured weight × valid support. Missing/zero/invalid evidence does not eliminate candidates; contributions/normalization/support are explicit. Partial support cannot report a complete score. Human-readable reasons separate historical openness and observation support.
- Historical masks are regenerated from pinned original imagery under one explicit spectral/cloud policy without modifying the original rasters. Missing requested dates reduce support. Source fingerprints, policy and original provenance are retained; unmapped obstacles remain unknown.
- New-region elevation can be acquired automatically. Existing selected sources receive a real AOI+halo coverage preflight. Automatic acquisition prefers a hash-identified covering local FABDEM, otherwise a bounded public Copernicus GLO-30 window, labelled DSM with explicit uncertainty. WorldCover is aligned to each acquired imagery grid. Context sources are acquisition-time snapshots, not falsely dated as historical imagery.

## Verification

The full backend run exercised 330 tests: 329 passed inside the sandbox; the sole HTTP test was denied loopback by the sandbox and passed unchanged with permitted loopback access. A subsequently added in-flight inspection regression passed with the engineering/review integration set (21 passed). Later scoring-completeness/wording checks passed (55 Python ranking checks and 24 application JS checks); source-date/API checks passed (35 Python checks). Full frontend run before the final explanatory sentence: 77 passed. Final current-tree results and real enrichment/UI evidence are appended below.

Live automatic DEM verification succeeded for a small area outside the existing local tile. Evidence is `../2026-10-17/live-dem-acquisition.json` (Copernicus GLO-30 DSM, metre units, output checksum). No satellite scan or active dataset replacement occurred during this smoke test.

Real Bhadra enrichment job: `5eedeec872f94e0d995ed8d7022661d9`, proposed dataset `bhadra-temporal-580354150707`; source active package remains `bhadra-v1-20260601-fabdem-20261013`. This job uses five older dated observations, 2,477 exact retained parent geometries and 13,150 measured slope subregions. It must be reviewed and explicitly accepted or rejected by the user; the agent does not accept it.

## Limits

No fresh full-Bhadra satellite detection was run. A future scan requires available provider evidence and may return a different candidate count under the conservative detector. Passing geometry/source checks does not measure real-world precision/recall, establish complete tree/building coverage or certify landing suitability. Terrain resolution, DSM uncertainty, historical land-cover age, acquisition-date context, unknown restrictions/heights and heuristic score weights remain visible constraints.

Final combined current-tree verification: **332 Python tests passed** in 99.09 seconds with local loopback permitted, and **78 JavaScript tests passed**. Logs: `data/validation/knowledge-delivery-python-final.log` and `data/validation/knowledge-delivery-node-final.log`. Warnings are upstream Rasterio/Affine deprecations and the existing explicit-layer advisory. No failed checks remain.

## Completed temporal backfill and resumed verification

The real enrichment completed with 78,135 dated observations and 15,627 temporal aggregates across five historical dates. Mean valid observation support is approximately 96.5%; this measures observation availability, not polygon accuracy. Exact retained geometry, measured features and lineage were compared across `terrain`, `zones`, `terrain_characteristics`, `zone_environment` and `lineage`. See `enrichment-preservation-proof.json`. Both package checksums were independently rechecked after resumption; current selection is unchanged and the proposal remains unpublished and pending.

A final slope-layer correction resolves the preserved source raster from enrichment metadata, allowing the new package to reuse measured slope without its own raster folder. The focused slope/dataset/review regression run passed all 19 checks after that correction. A fresh full-suite rerun is recorded separately in `data/validation/knowledge-resume-python-final.log`; the resumed frontend run passed all 78 checks in `data/validation/knowledge-resume-node-final.log`.

Interactive visual verification is **not complete**. On resumption, the browser security policy blocked acquiring the local HELPS tab. No alternate browser surface or indirect browser control was used. No screenshot is asserted as final visual proof. The user can inspect the pending proposal through **Data Engineer → Build knowledge → Review polygons**, then choose Confirm replacement or Reject this build. Neither decision has been taken by the agent.

Fresh resumed full-suite result: **333 Python tests passed** (122.45 seconds; 532 upstream warnings) and **78 JavaScript tests passed**, including the final enriched-slope regression. The local server was restarted and its listener verified at `127.0.0.1:5000` (server process 3844). Startup logs: `data/archive/runtime/knowledge-resume-20261018.stderr.log`. The remaining acceptance step is interactive map inspection and the user's explicit decision.
