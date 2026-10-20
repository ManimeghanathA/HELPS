# Conservative candidate screening — 13 October 2026

Changes are local in `HELPS - draft`, based on Neha_branch `236c34c`. They have not been pushed or merged. This milestone hardens candidate generation; it does not establish terrain accuracy or landing safety.

## Confirmed failure and immediate map correction

The reported `Bhadra_ZONE_000874` covers 50,552.9 m² and has a computed 140.6 m clear diameter. All 514 source pixel centres inside the polygon are SCL class 5. The previous classifier accepts all 514. Available OSM and Overture building footprints have no overlap with the polygon, so subtraction cannot remove the unmapped structures visible in the user's screenshot. A geometric clearance circle does not prove real-world clearance.

The stricter classifier accepts 261 of those pixel centres. The other 253 fail the vegetation ceiling. This is a screening comparison, not a corrected polygon or measured accuracy gain. A reviewed negative exclusion preserves the reported geometry and withholds the entire site pending independent verification. The loader applies reviewed exclusions to existing datasets too. Verified live: 2,483 polygons displayed; the reported ID is absent; the stored 2,484-polygon baseline remains intact.

## Implemented safeguards

- Default new runs use `conservative-ground-v1`: SCL class 5 only, NDVI ≤ 0.20, existing strict MNDWI water rejection and UNKNOWN handling. The calibrated profile remains explicitly selectable for comparison. Usable grass and some other open surfaces will be lost under this experimental rule.
- Building footprints receive a 10 m uncertainty margin in conservative processing. Water keeps the existing 5 m line half-width and 20 m setback. Facility points, lines and polygons receive a 20 m uncertainty margin. These fixed margins are heuristic, not surveyed obstacle dimensions or aircraft clearance standards.
- Required OSM layers are buildings, water, industrial and facilities. Missing/unreadable layers stop acquisition or processing. A present, successfully fetched empty layer is distinguished from a missing layer. Timeout/error responses are never treated as empty evidence.
- OSM requests have bounded provider attempts and request timeouts, with archived source responses. Required obstacle groups are acquired before optional context layers.
- New OSM and Overture queries include a 30 m metric halo and retain source geometry before exclusion buffering. Conservative candidates also withhold a 30 m AOI edge strip to accommodate older snapshots clipped to the AOI.
- Reviewed exclusion registries are selected spatially, so renaming the AOI does not bypass a known negative.
- Final audits reject non-open, UNKNOWN and cloud pixels; invalid geometry; failed area/clearance gates; duplicate IDs; mutual overlap; and overlap with buffered buildings or any prepared exclusion layer. Numerical geometric area tolerance is 1e-4 m², not permission for real obstacle overlap.
- Canonical publication writes a separate temporary file and atomically replaces the destination. The engine selects completed runs with passing audits and both final artifacts. Failed, running or incomplete output cannot become active merely because its directory is newer.
- Map and ranking use the same loaded, quarantine-filtered geometry. Full polygon rings and multipart geometry remain preserved.
- Summaries record the selected policy and margins, `accuracy_measured: false`, and `landing_safety_certified: false`.

## Verification and current limit

Final verification: 64 Python tests and 4 JavaScript tests passed. New regression failures were observed before implementing boundary protection, run selection, live quarantine and loaded-metadata consistency, then passed after implementation. Independent code review identified the exterior-hazard omission and a metadata/geometry mismatch; both were addressed. Run metadata now describes the engine's loaded dataset rather than a newer directory. The current canonical baseline is explicitly reported as `legacy_unverified`.

Live verification and pixel counts are recorded in `conservative-pipeline-evidence.json`. UI server: http://127.0.0.1:8766 (restarted with the verified code).

Full Bhadra regeneration has **not** completed. The committed OSM package lacks required industrial/facility layers. Attempts against overpass-api.de and overpass.private.coffee failed with HTTP errors or timeouts, including a bounded alternative GET attempt. The existing imagery and Overture inputs are preserved with hashes in the acquisition manifest; incomplete OSM is not registered as complete. No substitute empty layers or new canonical result were published.

## Remaining work to demonstrate correctness

1. Acquire complete obstacle sources, with provenance, then run the conservative pipeline over the full Bhadra AOI. Compare candidate retention, known-negative exclusion and all final audits against the preserved baseline. A reduction in count must not be called a false-positive reduction without labels.
2. Register the source imagery and independent reference imagery with stable landmarks and known dates before using apparent overlay discrepancies as classification evidence. Check CRS, raster grid and imagery date separately.
3. Establish an independent, stratified validation set covering water, tree cover, roofs, industrial surfaces, roads, actual open terrain and uncertain boundaries. The existing empty annotation layers cannot measure precision or recall. Manual labels are useful once image registration is established; automated processing cannot replace independent evaluation.
4. Add suitable licensed higher-resolution obstacle/canopy evidence. Sentinel imagery cannot reliably separate small structures and narrow tree lines. SCL, NDVI and MNDWI do not distinguish every industrial yard, roof or paved surface from bare ground. OSM and Overture are incomplete sources, even after a successful refresh.
5. Measure precision, false-positive categories, recall and uncertainty on held-out sites; calibrate thresholds and margins against that evidence. Retain uncertain terrain as withheld rather than presenting it as confirmed open land.
6. Apply the same policy and provenance across historical dates before joining temporal confidence to regenerated polygons. The separately repaired historical database still uses the original 4,130-candidate reference.
7. Implement actual elevation/slope, canopy/obstacle height and operational constraint evidence before presenting landing suitability. The current engine's diameter-derived slope estimate is not a terrain measurement.

The current live improvement is the confirmed negative's quarantine plus geometry fidelity. Broader physical accuracy remains unmeasured until source completion and independent validation.
