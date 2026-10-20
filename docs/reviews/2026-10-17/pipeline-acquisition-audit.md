# HELPS acquisition and polygon provenance audit — 17 October 2026

## Finding: active polygons are retained, not a fresh detection run

The active June 1 package was built in `retained` mode on October 13. Its source seed is the 2,484-feature calibrated dataset associated with revision 236c34c, SHA-256 `66f45ebd2f4d107a3bc9739bc4bd6c0719e4fb6f0ac82b67a80b903d2fd8f9d1`. Seven reviewed quarantines leave 2,477 parent candidates. Every active parent was compared with its source-zone geometry in the same CRS: all 2,477 have zero symmetric-difference area. No surviving parent boundary differs from that source seed. This establishes current geometry lineage, not how the earlier seed was originally produced or its physical accuracy.

Measured FABDEM terrain derivatives, characteristics and 13,150 slope subregions were computed downstream of the retained parent map. They do not reclassify or correct the parent boundaries. The current package has no normalized temporal tables. Its bytes and registry pointer were preserved by this audit.

Evidence: `pipeline-provenance-audit.json`, the active package's embedded build_spec, and its manifest/build-status files. Historical absolute paths inside the immutable package identify the old draft workspace; the canonical source hash matches the retained artifact now in this workspace.

## Earlier and current acquisition

| Evidence | Earlier mechanism / source | Current position |
|---|---|---|
| Sentinel-2 L2A blue, green, red, NIR, SWIR1, SWIR2 and SCL | Archived tiled download adapter; CDSE Sentinel Hub Process API (`sh.dataspace.copernicus.eu/api/v1/process`), client-credentials authentication | Generic acquisition supports AOI/date, tiled 10 m output, mosaicking, clipping and hash-checked reuse |
| Historical date discovery | CDSE STAC (`stac.dataspace.copernicus.eu/v1/search`) | Current monthly search uses CDSE Sentinel Hub Catalog; inspects a bounded two-date monthly shortlist with SCL. Not an exhaustive guarantee of the best day |
| OSM | OSMnx / Overpass; earlier six groups | Current bounded requests to overpass-api.de and overpass.private.coffee; buildings, water, industrial/facilities plus context. Complete layers required; provider failures are not empty evidence |
| Overture buildings | `overturemaps download --type=building` over AOI bounding box | Same CLI adapter, with a query halo and archived response; current release chosen by installed CLI, not a pinned historical observation |
| ESA WorldCover | Added single-date runner downloads windowed v200/2021 tiles from `esa-worldcover.s3.eu-central-1.amazonaws.com` and aligns them to imagery | This audit restores that preparation to the newer knowledge UI acquisition path. It remains 2021 evidence, not the observation-date truth |
| Elevation | Existing raw SRTM-like, NASADEM, Copernicus DSM and FABDEM tiles; local reprojection/clipping scripts | Active measured source is locally supplied FABDEM v1-2 (Bristol/Fathom). No generic automatic DEM downloader was found in the earlier or current application code |
| Reviewed negatives | Locally maintained GeoJSON | Retained mode excludes old IDs; fresh mode now applies negative geometry so changed IDs do not restore a known rejected site |
| Authoritative restrictions / obstacle heights | No complete automated acquisition demonstrated | Missing evidence remains unknown; successful OSM fetching does not establish complete coverage |

Current cached legacy OSM has water under `water_polygons`, but lacks industrial and facilities layers. A fresh run must reacquire complete required layers; this audit did not fabricate replacements or perform a new Bhadra acquisition.

## Fresh polygon formation path

1. Validate observation date, source hashes, required groups, CRS and spectral/SCL grid.
2. Classify imagery, reject water, preserve missing pixels as UNKNOWN, buffer cloud/shadow fringes by three 10 m cells.
3. Apply supplied/aligned historical land-cover screening.
4. Polygonize connected open pixels, repair/decompose geometry, clip to usable AOI.
5. Subtract mapped buildings and prepared water/industrial/facility exclusions plus reviewed negative geometries. Conservative policy adds uncertainty margins and withholds a 30 m AOI edge strip.
6. Apply 900 m² and 30 m dimension gates; remove narrow necks by erosion/reconstruction; calculate actual geometry-based maximum inscribed circle and reapply clearance gates.
7. Audit class/UNKNOWN/cloud overlap, mapped obstacles, mutual overlap, geometry validity, IDs and stored areas.
8. Derive measured DEM slope/elevation/roughness, connected slope subregions, context, dated historical overlaps and an immutable package. Activation is separate.

The stricter default (`conservative-ground-v1`, SCL 5 only, NDVI <= 0.20, supplementary WorldCover exclusions) differs from the calibrated seed policy. A new run can retain substantially fewer candidates. Neither candidate count nor passing topology audits measures physical precision/recall. Missing buildings/trees in the evidence can still produce false positives; older WorldCover can suppress genuinely open sites.

## Reproduced and corrected defects

- A finite spectral nodata sentinel could yield plausible NDVI/MNDWI and become OPEN. The raster reader now respects masks/nodata/nonfinite values across all six bands and propagates UNKNOWN.
- Fresh knowledge generation omitted reviewed exclusions. It now subtracts only quarantined/excluded geometries, independently of old IDs; accepted review records do not remove terrain.
- The newer UI acquisition path omitted WorldCover preparation and could reuse the baseline-aligned product on a different grid. Default acquisition now prepares WorldCover against the actual acquired imagery; explicit uploaded alternatives still undergo strict grid checks.
- Retained reanalysis generated its dated observation using a one-cell cloud buffer, versus three cells in fresh generation. Both now use three cells.
- Algorithm checkpoint identity omitted `scripts/pipeline` code, including polygon processing. It now includes that directory, preventing stale reuse after those changes.

## Verification and limits

Regression failures were observed before fixes. Focused verification: 74 Python tests passed, including real synthetic raster-to-polygon-to-DEM/slope-to-temporal-package execution. Provider orchestration tests substitute downloads; they do not demonstrate live provider availability. Full-suite verification is recorded below when complete.

No fresh full-Bhadra run, live source downloads, active geometry replacement, registry activation or scoring-policy change was performed. Temporal scoring/backfill and generic DEM acquisition remain distinct unfinished work; this audit does not claim them complete. Historic classifications use differing policies; temporal interpretation must disclose or harmonize those policies before treating results as equivalent evidence of persistence.

Final verification: `python -m pytest tests -q --basetemp data/validation/audit-full-20261017` produced 266 passes and one sandbox loopback denial (WinError 10013). The unchanged failing HTTP test was rerun with permitted loopback access and passed: 1 passed. Thus all 267 Python tests were exercised successfully across the two runs. No frontend files changed. The local Flask server was restarted with debug disabled to load these corrections; no build or scan was submitted.
