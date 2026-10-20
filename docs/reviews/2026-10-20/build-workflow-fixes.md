# Build knowledge workflow repair

The approved current dataset is `bhadra-temporal-580354150707` (June 1, 2,477 parents). Its package is unchanged: SHA-256 `8171ad24748ef12d24a10857fb76eca60679c25ae102a730b66e0711601513d0`.

## Date selection

The live workflow API returned HTTP 500 after temporal enrichment activation. It assumed `manifest.source_records` was keyed by asset slot; enrichment stores a list of historical observations. The API now handles both layouts without using older history as current-day SCL quality. Regression tests reproduce both list failures and preserve the minimum new date.

The frontend had also swallowed initialization failures while leaving search/build controls available. It now waits for workflow chronology, displays loading failures, guards selection/submission and moves the selected date into the processing form. A real-code DOM harness covers delayed and failed initialization and successful date selection.

Monthly new-scan searches now start strictly after the selected observation date. They previously recommended the already-active June 1 date even though builds correctly reject it. Explicit historical searches retain their requested range.

## Sentinel downloads

Job `7366a28eca9446b29654b4ba9318de8e` failed on its sixth Process API request with HTTP 429. No retry policy existed. The shared request helper now serializes download and optional SCL-inspection Process API calls, spaces requests, honors CDSE's millisecond Retry-After value and uses bounded backoff for rate limits and transient failures. Persistent failure remains explicit; it never produces empty substitute data.

Download checkpoints pin the complete dated request and returned file checksum. Reuse checks CRS, dimensions, bounds, bands, types and nodata. A partial scan can resume verified tiles; changed requests and corrupt files download again. Old tiles without verifiable request checkpoints are not silently trusted.

Provider semantics: https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Overview/RateLimiting.html

## Verification

- Full Python suite: 390 tests pass (`data/validation/build-workflow-full-python.log`).
- Full Node suite: 87 tests pass, including delayed/failed startup and date-selection behavior.
- Python regressions cover the enriched manifest, date-search chronology, provider wait units, bounded failure, resumable tiles, cache corruption and changed dates.
- Live workflow returns HTTP 200 with selected June enrichment and minimum new date June 2.
- Live catalog discovery succeeded without provider errors.
- A separate 40 m test patch within Bhadra downloaded actual spectral/SCL imagery for October 12. Both tiles were reused on a second call. Evidence: `data/validation/sentinel-provider-smoke-20261020/result.json`.
- No new knowledge scan was published or activated. Browser visual verification was not performed; frontend execution was checked in the DOM regression harness and backend checks used the live server.
