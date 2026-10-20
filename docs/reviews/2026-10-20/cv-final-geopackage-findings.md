# Supplied final vision GeoPackage: measured impact on HELPS

Input: `probably_final.qgz/probably_final.gpkg`, 2,430,738,432 bytes.
SHA-256: `575b980a4225eda768fd83fee29fbee2ae073bc8a578b8b256fb50290c14f634`.

This supersedes the missing-file and partial-archive coverage limitations in the earlier repository assessment. It does not establish semantic accuracy or implement a new knowledge pipeline.

## Source verification

The file opens read-only and SQLite `quick_check` returns `ok`. Its three expected layers use EPSG:32643. There are 112,283 open polygons (classes 3 and 4), 648,748 other polygons (classes 1,2,5,6,7,8), and one boundary. There are 1,861 distinct batch identifiers across both classified layers, consistent with a much more extensive merge than the supplied 537-batch archive subset. A batch count alone is not an independent global-coverage proof.

Reported class areas sum to the 1,107.328657 km² AOI. The actual spatial intersection audit establishes that 36.552923 km² of the selected June candidates is covered. The remaining 0.003858 km² lies outside the vision AOI; the audit did not find an additional unprocessed hole inside the candidate footprints. Cross-class overlap inside the candidates is below 0.000001 m². None of the source geometries queried for the candidate audit required validity repair. These checks concern the relevant candidate footprints, not a global topology audit of all 761,031 features.

## What the model says about the selected June map

The selected map is `bhadra-temporal-580354150707`, containing 2,477 parents and 36.556781 km².

| Vision classification within current candidates | Area, km² | Share of original candidate area |
|---|---:|---:|
| Bare/open ground plus crops/grass/low vegetation | 18.870650 | 51.62% |
| Trees/dense woody vegetation | 7.662406 | 20.96% |
| Uncertain/mixed | 9.972725 | 27.28% |
| Water | 0.046367 | 0.13% |
| Roofs, industrial and roads combined | 0.000775 | less than 0.01% |
| Outside the vision AOI | 0.003858 | 0.01% |

These are model labels, not independently verified truth. The full vision file labels only 317 building/roof polygons. Its accepted building references and contextual roof rules are strongly localized; the file is not demonstrated to be a complete building inventory. Our existing building exclusions remain necessary.

## Two subtraction policies

Identified-obstacle classes in this comparison are water, trees, roofs/buildings, industrial structures and roads (1,2,5,6,7). The strict `other_regions` policy also excludes uncertain class 8. Road handling is an explicit policy choice, not a vegetation-height measurement.

| Result | Original June | Subtract identified obstacle classes | Subtract all other, including uncertainty |
|---|---:|---:|---:|
| Area immediately after geometric subtraction, km² | 36.556781 | 28.847233 | 18.874508 |
| Completely removed original parents | — | 245 | 714 |
| Changed but nonempty original parents | — | 1,144 | 1,501 |
| Unchanged original parents | 2,477 | 1,088 | 262 |
| Fragments passing existing geometry checks | 2,477 original candidates | 2,207 | 1,664 |
| Original parents with a geometry-eligible fragment | 2,477 | 1,903 | 1,206 |
| Area after geometry checks, km² | 36.556781 | 27.897278 | 16.824860 |

The geometry checks reuse the current 900 m² area gate, 30 m minimum rectangle dimensions, 15 m inward/outward neck operation clipped to the candidate, and 30 m inscribed clear diameter. Counts describe geometry-only fragments, not fully rebuilt or operationally approved opportunities. Fragment counts can increase when a parent splits. No threshold was relaxed or tuned to achieve a count.

Intersecting with model-open classes directly retains 18.870650 km² before geometry checks. Its small difference from subtracting all other is the 0.003858 km² outside the vision AOI. This is why unknown coverage and AOI policy must remain explicit.

After the same geometry checks, model-open intersection yields 1,667 fragments from 1,205 parents and 16.804226 km². Small boundary differences can affect connectivity and hard-threshold outcomes; the difference in fragment counts is not an accuracy measurement.

## Previously flagged sites

`Bhadra_ZONE_000200` has approximately 8,442 m² and is wholly classed uncertain. Identified-obstacle subtraction leaves it unchanged; strict other subtraction removes it. Other previously flagged zones 000078, 000079, 000240 and 000529 have the same qualitative behavior. Zone 000647 retains about 19,181 m² under identified-only subtraction versus 11,626 m² under strict subtraction, from approximately 19,273 m² originally.

Consequently, known-class subtraction alone does not resolve all user-reported false positives. Conversely, uncertain is not established physical obstruction; excluding it can also remove real openings. A conservative review proposal may withhold uncertain terrain, but must preserve that reason and the baseline geometry rather than relabeling it as a detected building or tree.

## Artifacts and verification

All new outputs are under `data/reviews/2026-10-20-cv/final-gpkg-audit/`:

- `source-metadata.json`: source hash, class counts/areas, batch identifiers and SQLite check.
- `summary.json`: exact subtraction/coverage metrics.
- `per-candidate.json` and `per-candidate.csv`: class overlap and retained areas for every original parent.
- `geometric_comparison.gpkg`: raw geometric results for three policies.
- `geometry_gates_comparison.gpkg`: size/neck/clearance-filtered comparisons. These are analysis layers, not a knowledge package.
- `geometry-gates.json`: the corresponding geometry-check totals.

Both comparison GeoPackages also include `original_june_candidates` for direct overlay. The filtered comparison geometries were reopened and checked for validity, nonempty area at least 900 m² and stored clear diameter at least 30 m.

Area identities were independently checked: original minus identified classes equals identified-only retained area; subtracting uncertainty gives the strict retained area; the sum of open classes equals model-open intersection. All 2,477 per-parent retained areas are bounded by their original areas. The source file size and modification time were unchanged through intersection analysis.

The approved June knowledge package remains selected and unchanged, SHA-256 `8171ad24748ef12d24a10857fb76eca60679c25ae102a730b66e0711601513d0`. No new dataset has been registered or activated.

## Proposed next integration

Create a separately reviewable CV-assisted refinement build. Preserve identified-obstacle, uncertain and outside-coverage reasons separately. A strict preview can follow the user's current `candidate minus other_regions` proposal while retaining the identified-only comparison for review. Retain original-parent/child lineage and the baseline for recovery.

Before this becomes usable application knowledge, rebuild slope subregions and all geometry-dependent features, recompute historical overlap on the new footprints, apply the existing hard/soft recommendation logic, validate, and expose the ordinary map acceptance/rejection action. Preserve separate Sentinel observation dates and vision imagery date/unknown status. No assumption that these Esri-derived labels describe June 1 or current conditions is justified by the file copy/retrieval date.

This refinement can remove parts of existing candidates. Finding openings previously missed by Sentinel is a separate proposal-source extension and is not achieved through subtraction.
