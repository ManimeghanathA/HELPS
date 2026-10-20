# Assessment of the teammate vision workflow

Update: the final GeoPackage was subsequently supplied and audited. See [measured final-file findings](cv-final-geopackage-findings.md); its data supersedes the missing-file/partial-archive coverage limitations below.

Repository: https://github.com/Nehareddy1234/cv_ai_helps

Pinned revision: `47843a288f195e1bbb1eb2df7481d7ec255c9eb1`.

This is an assessment and proposed integration, not an implemented pipeline change. The selected HELPS dataset remains `bhadra-temporal-580354150707`; its SHA-256 remains `8171ad24748ef12d24a10857fb76eca60679c25ae102a730b66e0711601513d0`.

## Evidence examined

Relevant source and report files were downloaded to `data/reviews/2026-10-20-cv/repository`. All 95 downloaded text files were checked against the pinned repository Git blob hashes; SHA-256 records are in `reviewed-source-hashes.json`. Core segmentation, classification, batch, imagery and export implementations were reviewed. No external model code, joblib/pickle or installation script was executed.

The supplied `probably_final.qgz` is a directory containing `probably_final.qgs` and a styles database. Its four layers are the Esri basemap and three external GeoPackage layers: `bhadra_boundary`, `other_regions`, `open_regions`. All vector data sources point to `./probably_final.gpkg`. That file is absent from the supplied directory and the workspace search. The repository README says the final generated GeoPackage is intentionally not committed. QGIS layer declarations and stored extents are not the actual geometries.

## What the implementation does

1. Acquire Esri World Imagery in overlapping windows, preferring zoom 19 and falling back to 18. Reproject to EPSG:32643 at approximately 0.484993 m grid spacing. Native imagery detail/date is not established by that output spacing. The sample imagery metadata records retrieval time, not acquisition time.
2. Run pretrained SAM ViT-H automatic mask proposals. SAM proposes boundaries; it does not assign land-cover classes.
3. Compose a partition using SAM masks, accepted footprint geometry, Felzenszwalb image-edge gap completion and small-fragment cleanup. Preserve `origin` to distinguish these mechanisms.
4. Compute 16 RGB/color/texture/road-context features per pixel; predict with a scene-specific random forest and aggregate votes into regions.
5. Apply interpreted reference overlaps, footprints, confidence rejection and geometric/context rules. Preserve classes, scores, review status and provenance.
6. Clip each batch to its assigned core, with halos for context. Verify per-batch topology and publish transactional results. Batch-seam objects can remain split.

The eight-class schema is: 1 water; 2 trees/dense woody vegetation; 3 crops/grass/low vegetation; 4 bare soil/rock/sparse ground; 5 buildings/roofs; 6 industrial/engineered structures; 7 roads/tracks/pavement; 8 uncertain/mixed.

The random forest learns classes 1,2,3,4,5,7. Industrial labels come from references/review, and uncertainty from rejection rules. Roof and road acceptance depends strongly on nearby accepted footprints/corridors. Thus the model alone is not a drop-in replacement for the complete workflow.

The README also describes an independent SegFormer B2/ADE20K workflow in a sibling `ViT` directory. Its actual code is absent from this repository tree; it must not be confused with the SAM/random-forest batch output. The coarse whole-AOI SAM experiment is explicitly rejected/audit-only.

## Accuracy evidence and limitations

The saved scene forest uses 48,000 interpreted pixel samples. A repeating 192-pixel spatial block holdout reports 90.53% pixel agreement, macro F1 0.8891. This is agreement with interpreted labels from one scene, not independently established Bhadra-wide accuracy or candidate clearance. Reported bare-ground F1 is about 0.766 and roofs about 0.819. Road distance contributes about 21.89% of feature importance and uses reviewed road context also involved in label construction.

The original rectangle contains 2,634 regions, with 17.30% uncertain area. Its composition report attributes about 25.97% of pixels to initial edge gap completion. A geometrically complete partition is not the same as complete SAM identification or correct labels.

The batch feature windows at 3/9/21 pixels correspond to approximately 1.46/4.37/10.19 m at the trained sampling. At Sentinel's 10 m grid they become 30/90/210 m. Reflectance and rendered RGB also differ. Directly applying the same forest to upsampled Sentinel RGB is unsupported; upsampling does not recreate small obstacles. A new sensor/resolution requires corresponding training and validation.

## Local batch evidence

The six supplied archives contain exactly 537 unique batch verification reports, no duplicate batch IDs and no failed reports. All report the same classifier and pipeline hash. Their reported classified areas sum to 309.716878 km²; this is not an independently measured union-coverage result.

| Class | Reported area, km² | Feature count |
|---|---:|---:|
| Trees/dense woody vegetation | 255.052227 | 119,619 |
| Uncertain/mixed | 28.879856 | 77,786 |
| Bare soil/rock/sparse ground | 5.804217 | 10,500 |
| Crops/grass/low vegetation | 19.763040 | 10,205 |
| Water | 0.217539 | 315 |

No roof/building, industrial or road label is reported in these particular 537 batches. This does not prove those obstacles are absent; classifications may be uncertain or mistaken. The code's context-dependent rejection is relevant here. The combined team's missing final GeoPackage may contain other batches/classes.

The repository distinguishes an older 7-complete checkpoint, a later 542-complete checkpoint reporting 30.96% coverage, and a combined product with 1,074 batch-footprint records. The planned queue contains 1,860 entries. None of those counts alone establishes completed whole-AOI union coverage. The final combined product cannot be verified without its actual data.

Evidence: `data/reviews/2026-10-20-cv/local-batches-audit.json` and `qgis-layer-references.json`.

## Grouping semantics must be preserved

The per-batch `export_2layers.py` omits roads and uncertain from BOTH its obstacle and open exports. The later grouped README places uncertain in `other_regions`. Therefore those layers are not interchangeable exports.

`AOI minus union(open + low vegetation)` is an exclusion/residual mask. It can include real obstacles, uncertain classification, missing tiles and unprocessed land. It cannot be described as a detected-obstacle map. Within verified coverage a complement can be a deliberately conservative withholding policy, but this policy must be explicit and its loss of candidates measured.

The supplied QGIS project preserves original class/review fields in the two grouped layer schemas. Use those attributes to recover at least four internal states: mapped obstacle, plausible open/low vegetation, uncertain, and unprocessed/nodata. Two display colors must not erase those distinctions. Crops/low vegetation is a broad appearance class, not a measured vegetation-height guarantee.

## Proposed immediate integration

1. Obtain the real `probably_final.gpkg` and retain a hash-pinned source copy. Read class fields, CRS, validity, unique keys, source batches and source dates. Compare its AOI to HELPS and measure actual coverage, gaps, overlaps and batch seams. Do not infer coverage from the displayed map extent.
2. Build a spatial index of explicit obstacle classes. Preserve unknown/unprocessed areas separately. Decide how uncertain areas are withheld or displayed after measuring their impact, rather than silently turning them into obstacles.
3. Compute `current candidate minus applicable vision obstacles` in the metric CRS. Dissolve relevant masks locally by intersection, avoiding a needless whole-AOI union of hundreds of thousands of features. Preserve the original candidate IDs as lineage, with new child IDs for fragments.
4. Reapply usable area, width, neck removal and clearance checks. Subtraction may split, shrink or remove candidates; it cannot discover openings absent from the original candidate set.
5. Recalculate geometry-dependent measurements: area, reference point, inscribed clearance, slope subzones, roughness/elevation statistics, contextual features and temporal overlaps for each revised footprint. Do not copy parent scores or temporal percentages onto changed children. Keep existing hard/soft scoring semantics.
6. Produce an unpublished comparison: unchanged/changed/split/deleted candidates; removed area by class; unknown/unprocessed exposure; new feature measurements; source provenance and residual overlaps. Explicit map review precedes activation. Existing knowledge remains recoverable.

Do not union split fragments back across removed obstacles. Cross-core seams may be reconciled only where adjacency and class evidence justify it, retaining lineage.

## Proposed longer-term integration

Use complementary evidence with independent dates and quality records:

- Dated Sentinel observations: broad current surface condition, water/vegetation signals, cloud support and temporal persistence.
- Compatible high-resolution RGB + SAM/forest or a separately validated model: detailed structural boundaries and plausible openings.
- Existing mapped obstacles, DEM/slope, restrictions and mission/aircraft policies: retained evidence and constraints.

An old/unknown-date high-resolution opening does not establish a current opening. Recent strong contrary evidence must be surfaced. Conversely, a single vegetation-index threshold cannot establish the height of vegetation inside a high-resolution clearing. Preserve disagreement/unknown status instead of an unexplained average of unrelated confidence scores. No temporal history or soft score overrides an established hard obstacle.

A future model can use another imagery source only when band order, radiometry, resolution, georeferencing, contextual features and target-scene performance are checked. Dropping Esri does not remove the need for detailed imagery. If only Sentinel imagery is available, keep expectations at its observed resolution and train/validate for that sensor.

To recover missed openings later, evaluate vision-open areas as an additional proposal source, not solely an exclusion layer. Separate that experiment from subtraction-only recovery. Run expensive detailed inference on candidate surroundings and relevant changed areas where possible; cache by image/model/parameters and retain footprint-level acquisition/unknown dates. Do not claim full seasonal updates from rerunning on an unchanged basemap.

## Next required input

`probably_final.gpkg`, beside its QGIS project, is necessary to quantify the actual effect on HELPS candidates. The current review has not subtracted anything, changed the detector, re-run training, or modified/activated a knowledge package.
