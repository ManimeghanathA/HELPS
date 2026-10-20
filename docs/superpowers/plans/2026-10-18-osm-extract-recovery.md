# OSM Extract Recovery Implementation Plan

> Use superpowers:executing-plans and test-driven-development. User explicitly requested completing OSM acquisition and a newer-date knowledge build; preserve existing knowledge until explicit UI acceptance.

Goal: recover Bhadra with valid OSM evidence rather than repeated overloaded Overpass queries. Add a checksum-verified Geofabrik regional snapshot fallback and persist complete layer provenance. Current snapshot dates are not relabelled as the imagery observation date.

Constraints: retain original raw downloads; validate extract polygon covers AOI plus 30m halo; exact MD5/size validation over HTTPS and SHA-256 pinning; bounded/resumable transfer and disk preflight; no spatial filter that drops OSM referenced vertices; preserve points, lines, polygon holes and relations; all required groups must be produced from readable source; fail without publishing on errors; never replace active map automatically.

- [x] Test and implement bounded extract downloader/coverage reader in scripts/pipeline/osm_extract.py.
- [x] Test full-geometry, tag-preserving local group extraction with synthetic OSM data. Existing GDAL/Arrow streams each declared SQL layer without source spatial filtering; holes, explicit facility areas and linear overrides are covered.
- [x] Connect as automatic recovery in acquisition/region_inputs and retain provider/source snapshot provenance.
- [x] Acquire real source and validate all Bhadra layers, then build newer October 12 knowledge from cached Sentinel plus required inputs; leave pending review.
- [x] Run regression tests, verify protected package hashes, restart idle server and report actual pending build.

User refinement during execution: ordinary scans now use a Bhadra-only date form and a backend-enforced local-static-input policy. Only date-specific Sentinel may download; missing static evidence stops the scan. All feature, slope, temporal, scoring and review behavior remains present. Real job `7f4cf8106cfd4b029358f01813f7f7ed` / dataset `bhadra-20261012-623bdb28` completed valid and pending. See `docs/reviews/2026-10-18/date-only-completed-proof.json` and `osm-extract-real-proof.json`; final regressions 375 Python / 85 JavaScript.

Ruling: downloading the ~558MB regional snapshot is within the user's explicit request to obtain required OSM automatically. No new confirmation loop. It is cached once and bounded to 750MB per snapshot. No dependency installation unless required by verified parser capability.
