# HELPS — Helicopter Emergency Landing Place Suggestion System

HELPS builds terrain knowledge from satellite imagery, mapped obstacles and elevation, then explains helicopter-specific candidate recommendations. **Bhadra, India** is the working region. Main aircraft choices are **LCH, LUH and ALH**.

This handover is current as of **21 October 2026**. It separates implemented behavior, experiments and future work. HELPS is research decision support; candidate polygons are not certified landing sites.

## 1. Where the project stands

The user has **accepted** the vision-assisted revision. The selected dataset in the local registry is `bhadra-cv-20260601-313234b7`:

| Item | Value |
|---|---|
| Sentinel context date | 2026-06-01 |
| Candidate polygons | **4,474** |
| Measured slope subregions | **25,931** |
| Total candidate area | **28.364502 km²** |
| Refined fragments from previous candidates | **1,664**, 16.821074 km² |
| Additional vision-derived candidates | **2,810**, 11.543428 km² |
| Historical measurements | **152,025**, five dates for 30,405 terrain/zone entities |
| Vision imagery acquisition date | **Unknown**; not relabelled as June 1 |

`data/knowledge/registry.json` is the live authority; this README is a dated snapshot.

Do not confuse different versions:

- **2,484:** Neha's original calibrated June baseline, recovered and reproduced with pinned code and correct water/industrial context.
- **2,477:** retained June map after seven reviewed exclusions; source of temporal enrichment and vision refinement.
- **4,474:** accepted vision revision after subtraction, splitting, geometry checks and new additions. More fragments do not imply more usable area or measured accuracy.
- **October experiments:** conversation screenshots referred to roughly 533. Recovered-profile jobs inspected in this workspace have **577** candidates and 3,243 slope regions; stricter experiments produced 9 or 313. Identify an algorithm using dataset ID, sources, profile and manifest, not a remembered count.

Old/rejected/failed results remain preserved locally and do not become current automatically. [Delivery evidence](docs/reviews/2026-10-21-vision-refinement-delivery.md) records the vision proposal before its subsequent acceptance.

## 2. Start the application

### Existing Windows workspace

Open PowerShell in this root:

```powershell
.\launch.ps1
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000). Stop with Ctrl+C. `launch.ps1 -Port 5001` uses another port. The launcher installs requirements into `.venv` before starting Flask. Direct start with the installed environment:

```powershell
.\.venv\Scripts\python.exe -m flask --app app run --host 127.0.0.1 --port 5000
```

### Fresh checkout

The verified local runtime is Python 3.10.9. Manifests record library versions. Git LFS is required for existing tracked TIFFs:

```powershell
git lfs install
git lfs pull
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Do not overwrite an existing `.env`. Configure credentials if downloads are needed, then start Flask. Node.js is needed for frontend tests, not for running the app.

**A clone does not contain the complete local data workspace.** Knowledge packages, the 2.43 GB vision GeoPackage, team ZIPs, downloads and caches are excluded from new commits. Obtain matching data separately, preserve its layout and verify [the handover manifest](docs/data-assets-2026-10-21.json). Do not fabricate an empty registry or arbitrary map to make a clone appear populated. Historical immutable provenance can retain old absolute paths; deliberately relocate mutable routing without editing package bytes.

Providers: Copernicus Data Space/Sentinel Hub for Sentinel bands/SCL (`CDSE_CLIENT_ID`, `CDSE_CLIENT_SECRET` in ignored `.env` or local provider form); Open-Meteo for weather without a key; OSM/Overture/DEM/land-cover adapters for acquisition/maintenance. Ordinary Bhadra scans reuse local static evidence. Esri supplied the separate vision imagery; retrieval time does not establish acquisition date.

The application is a local loopback workspace. Engineer/application roles are workflow/API distinctions, not production multi-user authentication.

## 3. UI and users

The unified interface has **Overview**, **Map**, **Candidates**, **Application** and **Build knowledge** tabs:

- Map starts at India, allows Bhadra selection, shows candidate boundaries, features and measured slope.
- Candidates provides search/sort, expanded measurements and an inline selected-polygon map.
- Application shows aircraft dimensions/features, mission, typed coordinates or map-selected point, radius, weather and explained top-K recommendations.
- Build knowledge provides Bhadra date selection, monthly date search, input/storage readiness, durable processing, temporal enrichment and completed-map acceptance/rejection.

The original requirement distinguished a data engineer, who builds knowledge and can test recommendations, from an application user, who consumes them. These now share one application. Compatibility routes `/workspace/engineer` and `/workspace/application` remain; no separate draft checkout is required.

The current map display uses ceilings **0, 2, 4, 6, 8, 12, 15 degrees**; stored analysis also includes the **10°** threshold used by aircraft checks. Lower-ceiling areas replace overlapping larger-ceiling areas, giving the requested nested/onion shading. A ceiling is not an exact cell value. Unknown support and above-range terrain remain distinct.

## 4. All eight original phases

| Phase | Implemented responsibility |
|---|---|
| 1. Geospatial infrastructure | AOI, acquisition/import, CRS/coverage/nodata/date/hash validation and reusable storage |
| 2. Candidate terrain | Classification, polygons, obstacle subtraction, geometry filtering and lineage |
| 3. Characterization | Geometry, elevation/slope/roughness, surface observations, access and unknown fields |
| 4. Operational zones | DEM-derived connected slope regions, remeasured geometry/clearance and parent links |
| 5. Knowledge database | Immutable indexed GeoPackage, linked tables, provenance, integrity and active selection |
| 6. Recommendation | Validated inputs, retrieval, aircraft/weather/footprint gates, soft scores and explanations |
| 7. UI/integration | Map, candidates, recommendations, processing and explicit review |
| 8. Optimization | Indexes, bounded/cached requests, checkpoints, tests and source-pinned reproduction |

The [original V1 design](docs/superpowers/specs/2026-10-13-helps-v1-all-phases-design.md) records the earlier gaps and acceptance requirements. Its old status column is historical. Implementation does not establish ground firmness, obstacle height, approach clearance, complete legal coverage or authoritative aircraft limits.

## 5. Dated Sentinel pipeline

Default ordinary scans use **`neha-236c34c`**, recovered from Neha's commit `236c34c975f400f4a3bc636f6e431db2f1e75d66`. This includes geometry ordering, not only thresholds:

1. Resolve polygon/multipolygon **GeoJSON AOI** and date-matched Sentinel bands/SCL. Other vector sources need compatible declared layers.
2. Validate dates, bands/grid, CRS, nodata, coverage and required layers. File existence alone is insufficient.
3. Possible-open classification: **SCL bare soil 5: NDVI ≤0.50; SCL vegetation 4: NDVI ≤0.20; MNDWI <0**. Explicit water is excluded. Clouds/shadows/invalid observations and a **30 m margin** are unknown/unavailable.
4. Use **8-connected polygonization**, preserving recovered component/subtraction order. Later early repair/explosion changed the baseline and is disabled for this profile.
5. Work in metric **EPSG:32643**. Subtract buildings, water and industrial context. Water centerlines receive a **5 m buffer** and water exclusions a **20 m setback**. Missing required context fails; it is not silently empty.
6. Require **area ≥900 m²**, rotated-rectangle **length and width ≥30 m**.
7. Remove narrow necks: **15 m erosion → 15 m reconstruction → intersection with original usable geometry**. Measure maximum inscribed clearance; preserve holes/fragments.
8. Audit validity, overlap, unknown/cloud pixels and numerical tolerances.
9. Build DEM derivatives, slope regions, all features, environmental context and temporal overlap; validate/store immutable knowledge.
10. Preview the complete map; explicitly accept or reject. Processing alone never selects its output.

Read encoding metadata: detector/history masks use **0 not-open, 1 possible-open, 255 unknown**; some intermediate formats differ. They cannot be exchanged blindly.

The restored profile does not impose all later conservative WorldCover/facility experiments as hard candidate vetoes; those sources can provide context. Normal builds retain reviewed exclusions. See [baseline recovery and per-ID proof](docs/reviews/2026-10-18/neha-baseline-recovery.md).

### Why dates and thresholds matter

One algorithm can produce different June/October geometry because vegetation, water, clouds and source snapshots differ. Same-policy recovery measured 624,431 possible-open pixels after cloud buffering for June versus 88,138 for October. Count differences neither prove a bug nor establish accuracy; inspect source/date/profile/coverage and stage areas.

Sentinel pixels mix soil, roofs, vegetation and water. Spectral thresholds do not measure tree height or detect every small building. Threshold tuning cannot guarantee both complete obstacle exclusion and recovery of every useful brown patch.

## 6. Vision workflow and actual completed work

The teammate's [cv_ai_helps repository](https://github.com/Nehareddy1234/cv_ai_helps) was reviewed at `47843a288f195e1bbb1eb2df7481d7ec255c9eb1`. The output represents roughly **100 hours of team batch processing**, not automatic inference inside every HELPS scan.

### Model and source facts

- Esri overlapping RGB windows, zoom 19 preferred/18 fallback, approximately **0.485 m output grid**. This does not establish native detail or acquisition date.
- **SAM ViT-H proposes boundaries/masks**; it does not assign land-cover labels.
- A scene-specific **random forest**, 16 RGB/color/texture/context features, interpreted references and rules assign classes. Gap completion and core/halo clipping preserve batch lineage.
- Classes: **1 water, 2 trees, 3 crops/grass/low vegetation, 4 bare/open/sparse, 5 roofs, 6 industrial, 7 roads, 8 uncertain/mixed**.
- Reported **90.53%** block-holdout pixel agreement is scene-level interpreted-label agreement, not independent Bhadra-wide candidate accuracy. Roof/road acceptance partly depends on reference context. Only **317 roof-labelled features** exist in the final file; this is not a complete building inventory.

`probably_final.qgz/` is an extracted directory with a QGIS project and external `probably_final.gpkg`, not embedded vector data. The **2,430,738,432-byte** EPSG:32643 GeoPackage contains `open_regions` (**112,283**, classes 3/4), `other_regions` (**648,748**, classes 1/2/5/6/7/8), and one boundary. There are **1,861 distinct batch IDs**. Earlier checkpoint counts were partial products.

See [reviewed implementation](docs/reviews/2026-10-20/cv-integration-assessment.md) and [final-file audit](docs/reviews/2026-10-20/cv-final-geopackage-findings.md). Their dated findings distinguish initially missing data from the subsequently supplied file.

### Refinement completed 20–21 October

1. Pinned the GeoPackage checksum and audited layers, CRS, coverage and indexes.
2. Subtracted all applicable `other_regions` from the **2,477 current candidates**, reapplied mapped/reviewed exclusions and geometry gates: **1,664 fragments**, with 1,272 parents having no qualifying fragment left.
3. Contracted each vision open segmentation inward **5 m**, removed exclusions/already accepted geometry and reapplied strict geometry.
4. Required full valid DEM coverage and **every positive-area intersecting DEM cell ≤12°** for additions, as selected by the user. Highest admitted slope: **11.971163°**.
5. Added **2,810** sites with feature/class/batch/parent lineage and prevented duplicates.
6. Rebuilt all features, slope subregions, environmental and temporal measurements. Aircraft limits remain separate: configured LUH/ALH **10°**, LCH **12°**.
7. Created a separate source-pinned reviewed revision; preserved the previous package byte-for-byte. The user subsequently accepted it.

Uncertain class 8 is excluded under this approved strict policy. This is conservative withholding, not proof of a physical obstacle. Original classes remain in provenance. **Vision acquisition date is unknown. June 1 is Sentinel context, not demonstrated June imagery for every new site.**

Offline entry point:

```powershell
.\.venv\Scripts\python.exe -u -m scripts.knowledge.run_vision_refinement --max-slope 12
```

This producer targets the selected June baseline and pinned local assets. It is not general model inference/arbitrary-region/date processing and does not activate results. Do not casually rerun it against an already refined selection; establish the intended base and sources first.

## 7. Geometry, features and knowledge tables

A **terrain parent** is a candidate footprint. A **slope child/subregion** is a connected usable portion at a measured ceiling. Ceiling-specific regions can overlap; recommendation deduplication avoids repeating one opportunity.

| Feature group | Stored evidence |
|---|---|
| Identity/geometry | Dataset/source/parent IDs, boundary/holes, area/dimensions/hash, inscribed clearance/reference coordinate |
| Terrain | DEM source/resolution, support/sample counts, elevation/slope/roughness statistics |
| Surface | SCL proportions, observable/unknown fractions, NDVI/support/date, bare/vegetation/water fractions |
| Environment | Road/water proximity, available road/access tags, mapped occupancy/openness and restrictions/context |
| Temporal | Per-date open/not-open/unknown areas, coverage, dates/source IDs, confidence and support |
| Unknown evidence | Firmness, unsupported terrain, unverified surface/height/restriction values remain explicit |
| Vision | Origin, old parent, feature/class/batch, unknown acquisition date, addition slope evidence |

Tables include `terrain`, `zones`, `terrain_characteristics`, `zone_environment`, `lineage`, `sources`, `temporal_observations`, `temporal_aggregates`, dataset/run/parameters and spatial indexes. Actual foreign keys and integrity are validated. Geometry changes trigger recalculation; parent scores/percentages are not copied to fragments.

Current refinement uses covering FABDEM with a **30 m** terrain grid. Public fallback Copernicus GLO-30 is **DSM**, potentially including buildings/vegetation. Neither resolves every touchdown-scale hazard. [Elevation details](docs/automatic-elevation.md).

## 8. Temporal openness and updates

Historical **rasters** are measured against the **current exact footprint**, not just old polygon IDs:

```text
open_confidence = sum(historical open area) / sum(valid observed area)
support = sum(valid observed area) / (current area × available dates)
reported support also accounts for unavailable requested dates
```

Cloud/unknown area is excluded from open/closed evidence. Missing dates reduce support, not openness by inventing closed terrain. Current history: **2025-10-12, 2025-12-11, 2026-02-04, 2026-03-26, 2026-05-15**. Every current terrain/slope entity was remeasured. Masks are harmonized to the selected classifier/cloud policy and cache identity.

Temporal evidence is stored, explained and used as a **soft ranking factor**. It does not establish present openness, tree clearance or safety. A newer accepted scan preserves previous packages/classification sources for later comparisons; edited geometry is not a synthetic satellite observation. Same-date enrichment and pinned vision revision are reviewed exceptions, not a general date-rule bypass.

## 9. Recommendation gates and scoring

The engine retrieves measured slope opportunities, then checks request/aircraft/mission/weather evidence. Main choices are LCH/LUH/ALH; legacy profiles remain in compatibility code.

**Hard checks:** area, measured slope/support, clearance, exact aircraft footprint containment including holes, verified surface compatibility, restrictions and weather return **pass/fail/unknown**. Known failure excludes; soft score/history cannot compensate. Strict eligible results require passes. Research ranking can retain labelled unknowns, but never a known hard failure. Zero strict passes can coexist with promising research candidates. Ground firmness/obstacle heights are not silently verified.

**Soft score**, in `scripts/recommendation/ranking.py`, with mission weights in `helicopter_profiles.py`:

```text
score = 100 × sum(normalized_effective_weight[i] × supported_factor[i])
effective temporal weight = configured temporal weight × temporal support
```

Only supported, positively weighted factors participate; weights are normalized. Responses expose factors, contributions, configured/effective/normalized weights and supported-weight coverage. Missing factors are not invented. Factors include distance, clearance, area, slope, roughness, road proximity, mapped openness, water distance, surface, vegetation, weather and temporal openness according to mission. These policy weights are not learned safe-landing probabilities.

Missions: immediate emergency, precautionary/safest, medevac and balanced. Weather checks include location, time, units, heading/wind constraints. Nested opportunities are deduplicated. Reasoning preserves failures and unknowns. Do not weaken gates merely to populate results.

## 10. Storage, reuse and publication

```text
HELPSs/
  app.py, launch.ps1                  application entry points
  helicopter_profiles.py             aircraft/mission policy
  landing_zone_engine.py             GIS/compatibility integration
  weather_pipeline.py                weather normalization/acquisition
  scripts/pipeline/                  source resolution, acquisition, caches
  scripts/processing/                spectral/polygon geometry stages
  scripts/knowledge/                 terrain, features, temporal, DB/review
  scripts/recommendation/             gates, ranking, reasons
  scripts/ui/                         API and durable jobs
  scripts/archive/                    historical, not normal entry points
  static/, templates/                 unified frontend/retained legacy views
  tests/                              Python and frontend tests
  docs/                               handover, decisions, evidence, old plans
  data/raw/<region>/<source>/          downloaded/uploaded originals
  data/processed/<region>/            validated prepared inputs/dated imagery
  data/knowledge/                     immutable packages/jobs/sources/registry
  data/runs/                           polygon execution artifacts
  data/inputs/, uploads/              compatibility/staging where applicable
  data/cache/                          reusable request/provider data
  data/recovery/                       pinned baseline replays
  data/reviews/, validation/          local audits/tests/source review copies
  data/archive/                        preserved recovery/runtime/history
  probably_final.qgz/                 pinned local vision/QGIS data
  archive/                            earlier workspace material
```

Six loose team ZIPs now live in `data/raw/vision/batches/`; root change notes are in `docs/requests/`. [Move manifest](docs/workspace-moves-2026-10-21.json) records paths, byte sizes and verified hashes. Runtime/hash-pinned paths were preserved. [Workspace guide](docs/workspace-organization.md).

Reuse order is **validated processed → valid raw and local preparation → permitted acquisition**. Manifests, hashes, AOI/date/coverage/layer contracts determine reuse, not filenames. Partial attempts are not complete caches. Legacy Bhadra evidence was registered in place. DEM reference, mapped snapshot and Sentinel observation dates remain separate.

The ordinary **Bhadra date-only form downloads only missing Sentinel/SCL**. Missing static baseline evidence stops for maintenance/import. General adapters retain acquisition capabilities but the current form does not offer arbitrary new-region automation.

Monthly search distinguishes catalog cloud estimates from measured AOI SCL cloud/shadow coverage. Date selection waits for workflow initialization and reports errors. Ordinary observation dates must be newer than current context and no later than today.

Sentinel calls are paced/serialized with bounded retries, provider retry timing and request/grid/band/content cache checks. Overpass 500/502 failures were acquisition failures, not the disappearance of OSM. A checksum-verified Geofabrik regional PBF recovery established local context; routine date scans avoid new Overpass calls. Never replace missing context with empty masks.

Durable jobs live in `knowledge/jobs`. Checkpoints require matching source/algorithm fingerprints. Builds produce immutable `knowledge/<dataset-id>/knowledge.gpkg` and manifests. Preview tokens/current/package checks guard explicit acceptance. Failed/rejected builds preserve current selection. Never edit accepted bytes or rewrite checksums to bypass validation.

## 11. Project history and major changes

| Stage | Actual change |
|---|---|
| Original spectral work | Sentinel classification, polygons/building subtraction and reference outputs; obvious obstacles/missed openings exposed resolution/context limitations. |
| Neha calibration | Class-specific NDVI, water/industrial handling, cloud margin, neck opening/MIC/audits and satellite polygon UI; June result 2,484. |
| Strict experiments | Extra vetoes sharply reduced counts, including roughly 190 and 9-candidate attempts; user rejected sacrificing promising ground merely for a cleaner-looking map. |
| Full V1 | All eight phases, linked knowledge, real DEM/slope regions, environmental/temporal evidence, mandatory gates and soft ranking. |
| UI consolidation | One app; India/Bhadra map, aircraft details, point selection, feature inspection, onion slope bands, dark/light theme and review. |
| Input storage | Raw/processed manifests, reuse/coverage/date contracts and visible paths; existing sources retained in place. |
| OSM/date-only recovery | Verified extract recovery after provider failures; local static reuse with dated Sentinel downloads. |
| Baseline restoration | Recovered code/context and per-ID proof of 2,484; normal retained June 2,477 after exclusions. |
| Temporal enrichment | Historical area overlap added to reasoning/scoring without changing boundaries; reviewed revision. |
| Build/download fixes | Workflow shape/null date-selection errors, newer-date search, Sentinel 429 pacing/backoff and validated tile reuse. |
| Vision audit | 95 pinned source/report files reviewed; SAM/RF distinction, scene validation, missing dates, roof/context limitations and actual vector layers. |
| Vision refinement | Subtraction, contraction, strict geometry/12° admission and full feature/history rebuild; 4,474-candidate revision accepted 21 October. |

Reports under `docs/reviews/` describe dated evidence; `docs/superpowers/` retains historical designs/plans. Plans are not implementation proof. Current code, registry/manifests and final validation supersede old status statements. [Baseline recovery](docs/reviews/2026-10-18/neha-baseline-recovery.md) includes exact replay and missing-layer diagnosis.

## 12. Next pipeline question — proposed, not implemented

The expensive Esri segmentation is detailed but undated. Sentinel provides dated seasonal appearance but misses small obstacles. Neither alone establishes complete current suitability. The next design must reuse detailed evidence while updating current conditions:

1. Preserve detailed geometry/classes, uncertainty/coverage and source date-or-unknown. Do not rerun every expensive batch by default.
2. Produce dated Sentinel proposals and condition evidence, separating observable support, contrary evidence and cloud/unknown areas.
3. Evaluate detailed openings **and new dated proposals**. Blind intersection misses newly open land; blind union admits stale/unsupported land.
4. Define obstacle, disagreement and freshness rules. An old opening does not prove today's opening; undated obstacle evidence cannot automatically be assumed current forever. Disputed/detail-limited areas need compatible dated detailed imagery or verification.
5. Apply geometry, slope, mapped restrictions and aircraft checks; rebuild features/history/reasons; preview before acceptance.
6. Measure obstacle inclusion and missed-opening rates on representative held-out examples. Counts/topology tests are not detection accuracy.

The scene-specific RGB forest is **not validated on Sentinel's 10 m bands**. Radiometry, spatial feature scales and context differ. Upsampling cannot restore small obstacles. Compatible dated imagery, model adaptation/training and evaluation require a separate agreed design. The completed offline refinement is not automatic seasonal/vision model integration.

## 13. Code map, tests and troubleshooting

| Area | Main files |
|---|---|
| API | `app.py`, `scripts/ui/api.py`, `unified_api.py`, `analysis_jobs.py` |
| UI | `templates/unified.html`, `static/unified_core.js`, `unified_application.js`, `unified_build.js` |
| Inputs | `scripts/pipeline/region_inputs.py`, `source_store.py`, `acquisition.py`, `sentinel_requests.py`, `osm_extract.py`, `elevation.py` |
| Geometry | `scripts/processing/open_land_detector.py`, `candidate_polygonization.py`, `building_subtraction.py`, `candidate_geometry_filter.py`, `operational_zone_extraction.py`, `maximum_clearance.py` |
| Knowledge | `scripts/knowledge/build.py`, `dem.py`, `characterization.py`, `slope_zones.py`, `environment.py`, `temporal.py`, `repository.py`, `review.py` |
| Vision | `scripts/knowledge/vision_refinement.py`, `run_vision_refinement.py` |
| Recommendation | `scripts/recommendation/inputs.py`, `compatibility.py`, `ranking.py`, `weather_policy.py`, `helicopter_profiles.py` |

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
node --test tests/*.cjs tests/*.test.js
```

Refinement verification passed **401 Python tests, 87 frontend tests**, focused review, independent geometry/slope/features/history checks, HTTP page/review and all **4,474** GeoJSON boundaries. The detailed preview is approximately **72 MB** and can take time to load. Browser visual verification was unavailable at delivery; API/DOM checks do not imply manual visual inspection.

- **Zero strict passes:** inspect hard failures/unknowns; do not delete gates.
- **Different count by date:** compare observable area, inputs/profile and stage audits before changing thresholds.
- **Monthly SCL failure:** catalog estimates are not local QA; inspect provider/credentials/retry/cache evidence.
- **OSM failure:** use validated local static inputs; missing evidence requires maintenance, not empty layers.
- **Missing vision data after clone:** transfer the matching GeoPackage; QGIS styles/project are not the layers.
- **Relocated paths:** restore layout or deliberately relocate mutable routing without changing immutable packages.
- **Interrupted job:** inspect persisted status/checkpoint fingerprints. Avoid server restarts during builds; startup recovery can mark interruption.

## 14. Git and data handover

Source, tests, docs, sanitized summaries and already tracked reference assets belong in Git. Credentials, environments, caches, generated packages, downloads, vision GeoPackages and team archives remain local/separately transferred. Existing TIFFs use Git LFS. Ignore rules do not remove tracked files or rewrite history.

Use [data assets](docs/data-assets-2026-10-21.json) for paths/sizes/checksums and [move records](docs/workspace-moves-2026-10-21.json) for organization. Git push does not back up ignored data; keep a separately verified copy.

Further reading: [workspace](docs/workspace-organization.md), [inputs](docs/region-input-workflow.md), [elevation](docs/automatic-elevation.md), [baseline](docs/reviews/2026-10-18/neha-baseline-recovery.md), [vision findings](docs/reviews/2026-10-20/cv-final-geopackage-findings.md), [delivery](docs/reviews/2026-10-21-vision-refinement-delivery.md), [weather](docs/reference/weather-module.md).
