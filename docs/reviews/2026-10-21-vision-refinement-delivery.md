# Bhadra vision-refinement delivery

Completed 21 October 2026. Dataset `bhadra-cv-20260601-313234b7` is **unpublished and pending map review**. The selected June dataset `bhadra-temporal-580354150707` remains unchanged.

## Result

| Origin | Candidates | Area |
|---|---:|---:|
| Current June candidates after obstacle subtraction and strict geometry qualification | 1,664 fragments | 16.821074 km² |
| Additional vision open regions after 5 m inward contraction, exclusions, geometry qualification and maximum slope ≤12° | 2,810 | 11.543428 km² |
| Combined proposal | **4,474** | **28.364502 km²** |

All 2,477 current parents and 112,283 vision open segmentations were examined. 1,272 old parents had no qualifying fragment left. Individual source segmentations may produce multiple fragments. Counts therefore do not measure accuracy or imply increased usable area.

The proposal contains **25,931 measured slope subregions**. All previous terrain-characteristic and environmental feature fields are present and recalculated for the revised geometry. The recommendation formula, hard/soft feature treatment and aircraft-specific limits were not changed.

Temporal support was recalculated separately for every candidate and slope subregion: **152,025 observations**, covering 12 October 2025, 11 December 2025, 4 February 2026, 26 March 2026 and 15 May 2026. There are 30,405 entity measurements per historical date.

## Qualification and verification

- Excluded all vision `other_regions`: water, trees, roofs, industrial areas, roads and uncertain regions, together with existing mapped exclusions and reviewed rejects.
- Existing geometry rules: area ≥900 m², rotated-rectangle width and length ≥30 m, 15 m neck opening, and maximum clear diameter ≥30 m. Failing fragments are discarded.
- Every addition remains inside its individual source segmentation buffered inward by 5 m. Accepted candidates are subtracted before adding further sites to prevent duplication.
- Every positive-area DEM-cell intersection for an addition must have valid support and slope ≤12°. Actual highest admitted slope is **11.971163°**. The native knowledge terrain method and 30 m FABDEM grid are preserved.
- Independent checks passed for geometry, contraction containment, static exclusions, mutual overlap, slope, full DEM support, feature-field preservation, historical-date coverage and relational integrity. Maximum residual static overlap was 0.00000949 m² and mutual overlap 0.00000339 m², below the 0.0001 m² numerical tolerance.
- **401 Python tests and 87 frontend tests passed.** Focused code review found no important correctness issue.
- Live page returned HTTP 200. Review summary returned the correct counts and pending decision. The GeoJSON preview returned all **4,474** complete boundaries, including the correct origin counts and a review token. No acceptance request was made. Browser visual verification was unavailable in this session.

## Source and date provenance

Vision file: `probably_final.qgz/probably_final.gpkg`.

Vision SHA-256: `575b980a4225eda768fd83fee29fbee2ae073bc8a578b8b256fb50290c14f634`.

The vision imagery acquisition date is **unknown**. June 1 is the retained Sentinel context date, not a demonstrated acquisition date for new vision sites. This limitation is recorded per feature, in build parameters and in the review screen. Segmentation and DEM checks establish consistency with supplied evidence; they do not establish complete real-world obstacle detection or field landing suitability.

Active package SHA-256 remains `8171ad24748ef12d24a10857fb76eca60679c25ae102a730b66e0711601513d0`.

Proposed package SHA-256: `6f90f657eaec54a1c901b93907bd2a8f0e556264f6b976324a130c89ebbe883b`.

## Review

Open `http://127.0.0.1:5000`, choose **Build knowledge**, and inspect the pending proposal `bhadra-cv-20260601-313234b7`. Confirmation or rejection remains an explicit user action. Review job: `8e470f37024945088ddb6c619fad9997`.

Evidence is retained under `data/knowledge/bhadra-cv-20260601-313234b7/`: `refinement-input/refinement-audit.json`, `geometry-decisions.jsonl`, `refinement-spec.json`, `refinement-result.json`, `delivery-validation.json`, immutable package and manifest. API and test evidence are under `data/validation/vision-refinement-*`.

The independent delivery checker is `data/reviews/2026-10-20-cv/verify_refinement_delivery.py`. Model integration brainstorming follows this delivered refinement; the ordinary scan workflow was not replaced with an unvalidated vision-model integration.
