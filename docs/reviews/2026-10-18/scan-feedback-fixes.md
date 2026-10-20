# Monthly search and build-form feedback

## Diagnosis

The monthly date search previously did two operations together: catalog discovery/ranking and native-20m SCL ground-quality inspection of two shortlisted days per month. The catalog metadata is available independently; the repeated warnings came from the optional quality stage. Bhadra's native SCL extent is 1,861 × 2,861 pixels. This path submitted it as one request, unlike the tiled normal imagery downloader. The live failing request returned HTTP 400 (`COMMON_BAD_PAYLOAD`, invalid request). See `monthly-scl-failure-proof.json`.

The corrected path requests at most 2,400 pixels per dimension, validates every tile/grid/state, writes an exact 20m mosaic and publishes its cache only after successful quality measurement. The live October 12 test then succeeded: approximately 2.2315% AOI cloud/shadow, full AOI coverage. The 92.44% usable SCL ground support includes vegetation and is **not** a landing-suitability or polygon-accuracy metric. Evidence: `monthly-scl-tiling-proof.json`.

The failed October 12 knowledge job `d1f19cc66295485e97c355c8cff32746` stopped when both Overpass providers returned 502/500. These statuses establish upstream request failures, not their exact server-side cause. Large-query pressure can be mitigated; provider availability cannot be guaranteed.

## Fixes

- Date search now defaults to lightweight catalog estimates. Explicit optional regional cloud inspection performs tiled SCL requests. Estimated and measured results remain distinct. Search cache keys include the inspection option. Repeated quality warnings are consolidated; HTTP status/type is retained without exposing credentials.
- Overpass falls back to smaller queries after provider failures, with a 240-second per-layer budget, at most 32 HTTP requests, subdivision depth two and minimum-size limits. Complete child responses are deduplicated by element type/ID; tagged objects retain their tags when another child returns an untagged skeleton. Any unresolved child fails the acquisition; no partial/empty obstacle substitute is published.
- Raw query checkpoints include query and payload hashes. An interrupted adapter attempt can resume its own same-region/date/refresh-policy raw folder, while incomplete attempts remain ineligible as complete sources. Successful independent inputs are still reused through the source store. Refresh attempts never reuse complete older snapshots as if refreshed.
- Automatic source preparation displays elevation and optional restriction-area selection, instead of the advanced imagery/obstacle lists. Uploaded-files mode is explicitly advanced and requires user-supplied inputs. Saved-polygons mode explicitly keeps boundaries and recalculates features; it is not fresh detection.
- The elevation default now says it uses available elevation automatically, consistent with processed/raw/download resolution. Saved restriction areas can be selected, and a dedicated button opens upload for restriction/exclusion polygons. A missing registered restriction layer remains unknown, not verified clear.
- Previously quarantined/rejected polygon corrections remain automatically applied through the existing reviewed-exclusion source. They are described separately from restriction-area evidence and not misrepresented as a complete legal restrictions dataset.

## Verification and limits

Tests exercised oversized SCL tiling without coarsening or gaps, same-date cache reuse, Overpass subdivision failure, duplicate tagged/skeleton objects, resumable raw attempts and source-form progressive disclosure. Full results are in `data/validation/scan-feedback-python-final.log` and `scan-feedback-node.log`. No map/database acceptance or polygon replacement was performed. No live full-region OSM acquisition is claimed; recovery is covered by provider-simulated integration tests. Browser visual verification remains unavailable under the earlier local-page security restriction.

Primary reference for service output limits: https://github.com/sentinel-hub/sentinelhub-js (Sentinel Hub's own client documentation). Overpass query/resource settings: https://wiki.openstreetmap.org/wiki/Overpass_API/Overpass_QL.

Final results: **360 Python tests passed** in 57.19s; **83 JavaScript tests passed**. Active and pending package SHA-256 values were rechecked and unchanged, with the original dataset still selected. Updated server listener verified at `127.0.0.1:5000` (PID 16740). Runtime logs: `data/archive/runtime/scan-feedback-20261018.stderr.log` and matching stdout log.
