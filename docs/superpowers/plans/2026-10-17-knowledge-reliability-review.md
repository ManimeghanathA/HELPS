# Knowledge Reliability and Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Finish the user-approved temporal/acquisition workflow while preserving the retained map and requiring map-based review before every replacement.

**Architecture:** Immutable knowledge packages remain separate from selected registry pointers. Completed jobs enter pending review; engineers preview geometry/evidence then explicitly accept or reject. Temporal evidence is derived from historical rasters for exact entity geometry and participates only in soft ranking. Existing geometry-preserving enrichment is distinct from a newer satellite scan.

**Tech Stack:** Python, Flask, GeoPackage/SQLite, Rasterio/GeoPandas/Shapely, Leaflet and vanilla JavaScript.

**Spec:** User's approved five-step plan and 17 October explicit preview/confirm/reject request in this conversation; implementation details below are routine choices under that authorization.

## Global Constraints
- Preserve the active June 1 package and geometry; do not auto-activate scans or enrichment.
- New scans require strictly newer dates. Reopening an immutable June 1 version reproduces its geometry; do not promise the changed fresh detector reproduces it.
- Only hard features eliminate candidates. Temporal evidence remains soft; missing history remains unknown.
- Pending/rejected builds cannot enter recommendation queries or published historical evidence.
- Provider failures never become empty obstacle evidence. Source provenance, dates, coverage, units and hashes remain explicit.

## Review Focus
- A completed build cannot replace current knowledge without explicit acceptance after a successful preview.
- Rejecting a pending build is durable, preserves its artifacts for inspection and cannot activate it.
- Concurrent region changes or activation of another version cannot lead to acceptance of a stale preview.
- Temporal openness at low support must not overpower fully observed evidence; zero support contributes no evidence.
- DEM cache reuse must validate identity, regional coverage, nodata and units without treating DSM as surveyed ground.

## Tasks
- [x] Add regression-tested pending review API: geometry/counts/source/validation/comparison, review acknowledgements, accept and reject decisions, chronology and race checks.
- [x] Add a Leaflet build-preview map with candidate selection, feature details, counts, current-versus-proposed information and explicit confirm/reject actions.
- [x] Add coverage-aware temporal soft scoring and explanation; preserve all existing hard/soft distinctions.
- [x] Add automatic DEM acquisition/cache module and integrate it only when no covering chosen source exists.
- [x] Recompute consistent historical classification evidence and build an unselected geometry-preserving enrichment of the current package, with exact lineage/checksum validation.
- [ ] Verify backend/frontend regressions, review changes, restart local server, preview the pending enrichment without accepting it on the user's behalf.

Final task status on resumption (18 October): 333 Python and 78 JavaScript checks passed; server restart and listener verified. Interactive visual inspection remains unverified: browser security denied authority to access the local URL. Do not circumvent this restriction or mark the visual check complete. The completed enrichment remains pending for the user's map review.

## Rulings
- Pending package preview is read-only; publication/activation require an explicit review decision. No cleanup deletes rejected evidence.
- Use a separate enrichment operation for the same observation date, with strict geometry/feature preservation. Do not weaken normal new-scan chronology to permit duplicate-date scans.
- Score configuration weights are heuristic research policy, not learned probabilities; expose temporal weight, support and contribution.

- Ruling: historical observations are reclassified from pinned original spectral/SCL hashes under an explicit common spectral/cloud policy; mapped context and 2021 WorldCover are not historical observation-date obstacle truth.
- Ruling: requested-but-unavailable dates reduce temporal support without becoming closed terrain; package validation checks that support against normalized dated observations.
- Ruling: automatic Copernicus elevation is DSM evidence, explicitly labelled; it does not silently become bare-earth FABDEM.
