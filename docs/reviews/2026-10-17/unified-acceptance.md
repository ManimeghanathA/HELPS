# Unified HELPS acceptance — 2026-10-17

## Delivered requirements

| Request | Implementation and verification |
|---|---|
| One interface, no visible roles | Default and old bookmarked workspace routes serve the unified five-tab interface. Local mutation/same-origin guards remain enforced. |
| Branding and themes | Spaced HELPS wordmark, rewritten overview/core implementation copy, lime/sage/orange light palette and navy/magenta/teal dark palette, headlight control. Both themes inspected in browser. Aerospace cursor/scroll motion and rotor loaders support reduced-motion preferences. |
| Independent maps | Map and Application maintain independent regions/selections; Candidates creates an inline single-feature satellite map. Browser verified no tab change, full candidate boundary, in-tab recommendation selection/back and closable Map evidence note. |
| Automatic slope | Native DEM-cell bands clipped to exact parent boundaries, labels 0,2,4,6,8,12,15; separate >15 and unknown. No threshold selector. Tests cover exact edge classification, partition/non-overlap, holes, outside-support unknown. Stored legacy 10-degree analysis rows are retained. |
| Application inputs | Only LCH/LUH/ALH; model dimensions or validated manual overrides; typed coordinates or confirmed region-only map picker; optional heading for crosswind. Browser verified confirm enabling, coordinate commit and cancel preservation. |
| Explained ranking | Real observed engine phases appear in results panel. Short labels/cards retain full source IDs, features, hard gates, soft factors, weights and contributions in expandable evidence. No scoring/gate formulas were changed for the unified interface. |
| Knowledge workflow | Region upload, required named source choices, masked local provider credentials, monthly search range, dated cloud inventory, validated upload/process/review/current workflow. Only strictly newer current observations are accepted; failed builds and historical imports preserve current knowledge. |
| Source usability | Valid date/source selections survive uploads; dated spectral/SCL choices filter by observation. Current/past observations are separated without duplicate current history rows. |
| Repository consolidation | One runnable project and one Python environment at HELPSs root. Duplicate draft checkout/environment and generated review work removed after source/Git recovery and SHA-256 data-transfer checks. Original reports/requests are under docs. All scientific history preserved. |

## Fresh verification

Canonical root commands:

```powershell
.\.venv\Scripts\python.exe -m pytest -q --tb=short -p no:warnings --basetemp=scratch/final-tests
node --test tests/*.cjs tests/*.test.js
```

**261 Python tests passed; 68 JavaScript tests passed.** Local-server socket tests ran with network access; no tests were skipped. Browser QA covered both themes, all five tabs, populated candidates/inline satellite map, automatic slope legend, Map note close, independent Application region, coordinate confirm/cancel, actual recommendation progress/result/selection/back and scan inventory. At a 390px viewport, overview and Application had no horizontal overflow; viewport was reset afterward.

A real retained-package assessment at 13.8194 N,75.6659 E, ALH/balanced mission, radius2km, heading270 assessed298 zones and produced80 distinct research opportunities. Top scores:82.9523,81.6639,80.5444. There were0 fully passing opportunities; missing verification remains explicit. Research ranking never relabels these as operationally cleared. Full result and actual phase history: `live-assessment.json`.

The immutable active GeoPackage SHA-256 remains `0ded087336e671d5e7c1f2cb12ab84a62c94077055aff979ed79dfa86d02ebd9`; current observation2026-06-01,2,477 retained candidate terrains,13,150 measured slope zones. No new package was activated during this delivery.

## Measured local scan QA

Measured against the actual AOI using each dated SCL raster; coverage99.967184% for every scan, with uncovered area remaining unknown. Values below are cloud/shadow area as a fraction of the full AOI, not a guarantee of unobstructed ground.

| Observation | Cloud/shadow |
|---|---:|
|2025-10-12|2.850490%|
|2025-12-11|0.000036%|
|2026-02-04|0%|
|2026-03-26|0%|
|2026-05-15|1.288488%|
|2026-06-01(current)|7.746727%|

QA is cached outside immutable packages and invalidated by source/AOI identity. Copernicus credentials are configured; read APIs return only masked status.

## Scope of verification and retained limitations

The current broader candidate map is retained as requested. This UI delivery does not establish individual tree/building absence or resolve mismatches between imagery dates. The30m DEM and mapped/spectral sources still have observation-resolution/completeness limits; missing firmness, restrictions, obstacle-height and other verification remain visible. Recommendations are research evidence, not landing safety certification.

Provider acquisition/search and new-region build/publish contracts were tested with controlled provider boundaries. A full new AOI satellite download/build/activation was not run in this delivery. Real local six-date QA and the real recommendation assessment were run. The first uncached scan inventory measured six rasters in~75s; persistent QA reuse avoids that repeated work. External imagery/weather/provider availability still depends on network/services.

Recovery includes both original Git histories, original source snapshots and conflicting original data; see `data/archive/recovery/2026-10-17-unified/`. Mutable routing was relocated; immutable provenance retains historical acquisition paths. No remote push or deployment was performed.
