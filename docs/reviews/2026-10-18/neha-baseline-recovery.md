# Recovery of the 2,484-candidate June baseline

Recovered revision: `236c34c975f400f4a3bc636f6e431db2f1e75d66` (Neha).
Default production profile: `neha-236c34c` in both the application build API and pipeline CLI.

## Reproduction evidence

The original code and input hashes are retained in `data/recovery/neha-236c34c/recovery-manifest.json`. Frozen source files were extracted into that isolated directory without resetting the working repository.

The committed OSM file has no named water/industrial layers. The old reader silently treated these as empty and produced 2,694 candidates. With the recovered local water/industrial context, the frozen code reproduces **2,484** candidates, all original IDs, and 36,683,251.479369394 m² against the reference 36,683,251.479395226 m². Total symmetric boundary difference is 0.000026064642130972947 m². This is numerical rounding, not a count-targeted approximation.

The current production implementation also reproduces **2,484** using the same pinned inputs and recovered context. Its replay summary is `data/recovery/neha-236c34c/2026-06-01-recovered-context-replay-restored-profile/replay.json`.

Per-ID production verification is recorded in `june-restored-per-zone-proof.json` beside that replay, with a repeatable `verify_restored.py` comparison. All original IDs match. The full Python suite passes: **382 tests**, recorded in `data/validation/neha-restoration-final-python.log`. Regression coverage includes preserving the original diagonal-connected component until obstacle subtraction, and all three historical classification profiles with source immutability/cache reuse.

## Restored sequence

1. SCL bare soil: NDVI ≤ 0.50; SCL vegetation: NDVI ≤ 0.20; MNDWI < 0; explicit water rejection and 30 m cloud/shadow margin.
2. Original 8-connected polygonization, retaining connected components until building subtraction. Later early geometry repair/explosion and additional AOI clipping are disabled for this profile.
3. Subtract building footprints, water (5 m linear buffer plus 20 m setback), and industrial polygons.
4. Require 900 m² and 30 m minimum rotated rectangle dimensions.
5. Erode 15 m, reconstruct 15 m, intersect the candidate, and measure maximum inscribed clearance.
6. Validate topology, obstacle overlap, and unsupported pixels.

Later broad facility and WorldCover hard exclusions are not applied by this profile. Those sources remain available as knowledge features. Reviewed rejected sites remain excluded in ordinary application builds; the forensic replay intentionally excludes those later edits to establish the original result. That explains 2,484 original versus 2,477 retained June parents.

Nodata handling fixes, explicit missing-obstacle failures and stronger audits remain. We do not restore silent empty obstacle fallbacks. Historical masks use the same selected spectral/cloud policy, retaining the profile identity in cache provenance. DEM, slope subdivisions, environmental features, temporal support and recommendation hard/soft scoring remain part of knowledge building.

## Publication and interpretation

Replays never publish. New application builds require map review and explicit acceptance; rejection preserves the current knowledge base. A different date can yield fewer or more candidates under exactly the same algorithm. Candidate geometry is not proof of obstacle-free ground or operational landing clearance.

The 2026-10-12 normal application build `bhadra-20261012-f73274d5` generated **577** candidates (2.770178560407322 km²), including the seven reviewed exclusions. Its geometry audit passes. Same-policy open pixels after the cloud margin are 624,431 for June and 88,138 for October. These are measured source-classification differences, not a guarantee that every remaining polygon is suitable. The active June package remains selected and its SHA-256 remains `0ded087336e671d5e7c1f2cb12ab84a62c94077055aff979ed79dfa86d02ebd9`.

The October knowledge build completed with 3,243 slope zones, 22,920 temporal observations across six available historical dates, and valid history for all 3,820 terrain/zone entities. It remains pending explicit review. The historical profile allowlist fix was applied before historical import/execution in this build; its build-start implementation fingerprint predates that registration-only fix, while each historical cache identity records the updated execution fingerprint. Candidate code did not change during the run. Future scans start with the final implementation fingerprint.
