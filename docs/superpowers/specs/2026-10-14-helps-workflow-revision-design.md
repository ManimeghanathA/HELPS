# HELPS workflow revision

Design for the user's requested replacement of the confusing recommendation and engineering workflows. The previous full per-polygon feature inventory, linked geometry tables, mission factors and source provenance remain mandatory. No product implementation under this revision has started.

## Verified baseline

The original workspace is `C:/Users/manim/OneDrive/Desktop/HELPSs`; implementation remains isolated in its `HELPS - draft` clone. The original `data/processed/Bhadra/sentinel2/history_dates.json` declares historical observations 2025-10-12, 2025-12-11, 2026-02-04, 2026-03-26 and 2026-05-15, and current reference 2026-06-01. Corresponding date folders exist, as do candidate databases for June 1 and its corrected October 13 processing run. Folder presence is not sufficient evidence of a valid observation.

The draft's registered current Bhadra package also declares observation date 2026-06-01. Its October 13 build date is not the observation date. The original temporal implementation measures current polygons against dated historical classification rasters; confidence is summed open area divided by summed valid area, and support is summed valid area divided by candidate area times observation count. Cloud/unknown areas do not count as rejection. That implementation is currently disconnected from the draft package and recommendation pipeline.

The current acquisition API processes one supplied day. It does not implement a twelve-month monthly search. Version activation preserves prior immutable packages but does not compute temporal evidence or label a temporal timeline.

## Application User

Keep role entry and India overview, then choose a published region. Show current observation date prominently and historical versions in a clearly labelled history control. Main actions are Recommend, Browse Candidates and Map. Hide internal parent/child terminology, asset IDs and JSON configuration from normal navigation. Geometry relationships remain in storage and a technical export.

### Aircraft and position

The dropdown contains LCH, LUH and ALH only. Preserve stable internal IDs for compatible saved inputs. A selected-aircraft card shows model name, dimensions, clearance diameter, usable area, slope/wind limits, cruise speed and supported surfaces. Distinguish dimensional specifications from unverified configured research limits. Display the actual effective settings consumed by the engine; changing aircraft refreshes the card. Validate dimension provenance against HAL primary sources before presenting figures as authoritative.

Users can enter latitude/longitude, choose Select position on map, click a position, or drag the aircraft marker. All methods synchronize coordinates and marker; recommendation results preserve the query position. Ordinary polygon clicks continue selecting polygons unless position selection is explicitly enabled.

### Recommendations and explanations

The main output is Top terrain candidates for the selected aircraft and mission, with rank, relative score, distance, measured maximum slope, clearance and concise reasons. Selecting a result opens its full boundary, reference point, required circular footprint and reasons panel. Distinct opportunities are deduplicated across nested thresholds; use counts of distinct locations rather than raw nested records as the main summary.

Separate research ranking from verified operational eligibility. Known mandatory failures (incompatible measured slope, inadequate dimensions, footprint crossing boundaries, known prohibited surface/restriction, known incompatible weather) exclude a candidate. Candidates with unknown firmness, restriction coverage, canopy/height or weather may appear only as research candidates with prominent Requires verification badges naming the missing evidence. Unknowns are never converted into passed gates, favourable scores or certified clearances. Verified eligibility remains separately available as a factual assessment status. If no research candidate survives known failures, explain those failures and search coverage rather than say only zero passing.

Preserve all eleven balanced factors: distance, clearance, weather, area, slope, roughness, spectral surface indicator, vegetation indicator, mapped access, supported openness and water proximity. Retain other missions' declared priorities. Use only supported factors, output available/missing factors and normalized contributions, and display incomplete evidence beside the relative score. Temporal evidence is a separate visible confidence/support measure initially; adding an uncalibrated twelfth weight is outside this revision. Scores are not probabilities.

Remove Advanced evidence and policy options and raw JSON inputs from normal UI. Research policy remains explicit, validated and versioned on the server. Keep readable aircraft adjustments only where needed; retain full evidence through downloadable reports. Missing provider weather gets a precise status, not an ambiguous successful-weather claim. Display timing and location coverage.

### Exclusive slope bands

Display exact 0 degrees, (0,2], (2,4], (4,6], (6,8], (8,10], (10,12], (12,15], and >15 degrees where measured. Unknown support uses gray. Assign one consistent colour to each interval, progressing from flat green to steeper orange/red. A layer legend shows numeric ranges.

Within candidate boundaries, the set for an upper threshold excludes all lower-threshold sets: e.g. the 4-to-6-degree shade is the <=6-degree set minus the <=4-degree set. Use native measured slope cells clipped to candidate boundaries to ensure mutually exclusive area bands; do not overlay cumulative polygons or recolour an entire polygon from its mean slope. Preserve excluded holes and unsupported cells. Operational child geometries remain separately stored and used for aircraft checks, because minimum area/clearance filtering can remove fragments from cumulative threshold sets. No smoothing or interpolation invents sub-grid precision. Threshold 0 may legitimately contain no measured cells.

## Data Engineer wizard

Data Engineers can also use recommendations. Replace asset-ID/JSON forms with steps:

1. Region and current knowledge: show the active observation date, existing historical dates and reusable local sources.
2. Find imagery: search the twelve calendar-month buckets ending at the user-selected search end date; show each month's available observations, acquisition dates, cloud metadata and coverage. Partial first/last months follow the actual search interval. Months with no usable observation remain missing.
3. Choose observation: recommend the best usable day per month, then select the new current observation date. Past dates are reference evidence, never eligible as the new current version.
4. Sources: reuse approved DEM and available contextual sources, or choose named uploads. Group advanced source inspection in collapsible details. Show Available, Missing or Failed by source, dates and completeness. Reuse the original dated Sentinel/SCL/classification history read-only after validating grids, dates, hashes and coverage.
5. Build: acquire the selected observation, generate its own candidates, compute all geometry/terrain/context features, operational zones and temporal evidence. Show human-readable progress stages and useful failures; internal assets and IDs are assigned automatically.
6. Review and make current: show counts, area, measured-support and temporal-support summaries, source limitations, and change from the previous version. After validated publication, explicitly activate with Make current. Previous versions become historical in the UI while their immutable files remain unchanged.

Default new builds generate polygons from the selected date. Reusing retained geometry is a labelled reanalysis, not a fresh-date detection. Spectral/SCL observation dates must match the chosen date (or declare a bounded explicit composite with actual contributing dates); never relabel June data as a later observation. Engineering import remains supported through readable file selectors, without requiring users to know registered asset IDs.

### Monthly quality selection

Use authenticated Copernicus catalog search, retaining product IDs, timestamps, AOI coverage and metadata cloud fractions. Catalog cloud percentage is a shortlist signal, not a claim of AOI-specific clear ground. Inspect selected/shortlisted SCL data over the AOI to measure usable ground support/cloud-shadow proportion. Rank monthly days primarily by usable AOI support, then cloud-shadow burden, then coverage and deterministic date/product ties. Group same-day products needed to cover the AOI; account for gaps and overlapping tiles once. Present whether the quality is metadata-only or measured. Cache results and staged downloads; record failed/unavailable months and bounded provider errors. No credentials or hashes appear in normal UI.

## Date and publication invariants

New knowledge requires an observation date strictly later than the region's current active date and no later than the available observation date/today. For the inspected Bhadra baseline, the earliest permitted date is 2026-06-02. Apply this in the date picker, job submission, publication and activation, including rechecking at activation in case another newer build has become current. Equal-date and older-date normal builds return useful errors. A different region with no current version can build its first validated observation.

Processing timestamps never replace observation dates. Historical evidence discovery/import does not create a new active knowledge version and is permitted for dates before current. Reanalysis of an existing observation, if supported, is separate from New knowledge and never silently bypasses the monotonic date rule. Historical browsing is read-only. This revision does not expose rollback activation through the normal wizard.

Build and validate a new package without modifying current data. A failed source search, build, validation, publication or stale activation leaves the current package and its history intact. Atomic activation updates the current pointer and records the previous current version as historical; it does not physically move or overwrite source/package files. Existing dated folders are imported as evidence with their provenance, not reorganized or deleted.

## Temporal evidence and storage

Validate original classified raster artifacts before use; recover source dates/grids/hashes from manifests where available and mark unknown provenance explicitly. Do not attach the original candidate database's aggregates to new polygons by ID, count or row order. Recompute overlap against historical rasters for each new current polygon, preserving unknown support and excluded interiors. Process in windows or batches to keep native-raster area accounting bounded.

Store normalized observations keyed by dataset, stable entity ID, observation date and source identity: open/valid/unknown area, coverage and QA. Parent and operational-zone aggregates retain history dates/count, open confidence, valid support and source links. Only dates strictly earlier than the new observation contribute to historical persistence; same/newer dates cannot become history. Preserve the existing five historical observations and add the previously current date when a newer version activates; twelve-month discovery supplies additional validated dates without double-counting same-day acquisitions. Keep history for older versions immutable; moving the current pointer does not rewrite old temporal aggregates.

Separate: historical knowledge versions for browsing; historical rasters used as observation evidence; temporal persistence measured on current geometry. A source timeline can contain many days, whereas each current polygon has dated evidence and aggregates. Historical confidence is a persistence indicator, not proof of current absence of obstacles or permanence of terrain.

## Verification and acceptance

Test each data/consumer contract, then browser-test both roles on populated Bhadra data. Required cases: only three aircraft and card consistency; click/drag/typed coordinate synchronization; no known failed candidate recommended; unknowns remain explicit and separately classified; full factor inventory and contributions; exact holes/MultiPolygon geometry; disjoint slope bands with total measured area conservation and distinct unknowns; monthly missing/cloud/gap/product cases; current/older/equal/future date rejection; activation race; failure preservation; original-history read-only reuse; current geometry versus historical raster accounting; zero-valid confidence null; temporal denominators and source identity; no row-order joins; absence of JSON/asset-ID inputs in the normal wizard; responsive navigation.

Run one real small-area history integration before a full Bhadra rebuild, recording source license/provenance, entity counts, temporal support and timings. Network/provider access may limit acquisition, but unavailable inputs must be visible rather than fabricated. Keep the existing current Bhadra map until a newer valid observation is built and explicitly made current.
