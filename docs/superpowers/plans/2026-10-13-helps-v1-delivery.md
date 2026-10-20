# HELPS Full V1 Delivery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Implement all original HELPS phases with the retained parent map, measured terrain knowledge, mandatory compatibility checks and the user's two-role application flow.

**Architecture:** Preserve the accepted candidate dataset as immutable parent terrain. Build a versioned offline knowledge package, consume it in the online recommendation engine, and expose role-specific engineering and application-user workspaces. Dataset activation is explicit.

**Tech Stack:** Python 3.10+, NumPy, Rasterio, GeoPandas/Shapely, GeoPackage/SQLite, Flask, existing weather module, Leaflet and plain JavaScript.

**Spec:** `docs/superpowers/specs/2026-10-13-helps-v1-all-phases-design.md`.

## Global Constraints

- Retain the 2,484 source polygons and seven reviewed quarantines; 2,477 parent candidates remain the working map.
- The 191-candidate experiment is not an adopted replacement.
- Use research slope thresholds `[0, 2, 4, 6, 8, 10, 12, 15]`; preserve nested threshold relationships.
- Compute metric Horn 3×3 slope and detrended-plane RMS roughness at approximately native DEM resolution; withhold invalid neighborhoods.
- Source hashes, dates, units, coverage and unknown fields are mandatory. No invented slope, firmness, height or favourable weather defaults.
- Ranking cannot compensate for a failed mandatory gate; preserve parent browsing even when no child is eligible.
- Roles: Data Engineer includes engineering and recommendations; Application User includes published-data recommendations/candidate/map views only.
- This is local research decision support; configured compatibility and geometry do not establish physical clearance or legal permission.
- Preserve original workspace, uncommitted fixes and source files. Work in the existing separate draft clone on `codex/v1-all-phases`; publish nothing remotely without a separate request.

## Review Focus

- A new run or another AOI must never silently replace the selected Bhadra map: test explicit activation in the knowledge plan.
- Small/holey polygons on a coarse DEM must preserve unknown support and excluded interiors: test sampling/zones/footprints.
- A historical or missing weather snapshot must not appear as current favourable weather: test online policy and UI dates.
- A user-supplied invalid source/profile must yield a useful error while preserving prior knowledge: test input validation and job/publication failures.
- Switching role/region/view during a pending query must not show stale results for another dataset: test request identity and workspace state.

## Subsystem Plans and Dependencies

1. `2026-10-13-helps-v1-terrain-knowledge.md`: source contract, real terrain features, slope child zones, environment, persistent knowledge and explicit selection. Owns original phases 1–5 and offline phase-8 checks.
2. `2026-10-13-helps-v1-recommendation.md`: validated profiles/weather, indexed retrieval, hard gates/footprint and explained mission ranking. Consumes the knowledge repository; owns phase 6.
3. `2026-10-13-helps-v1-role-workspaces.md`: role entry, engineering form/jobs, India→region navigation, recommendations/table/map, slope shading, exports and clean startup. Consumes both contracts; owns phase 7 and online phase-8 checks.

Contract tasks precede their consumers. DEM/features and repository implementation can progress independently after shared contracts are pinned. Frontend shell can be built against explicit fixture contracts while backend integration is completed; fixtures are never published as real terrain evidence.

## Delivery Gates

- [x] Review this written plan and select inline execution in this chat or scoped parallel implementation.
- [x] Complete each task's red/green tests and scoped review; commit only the reviewed task files.
- [x] Build Bhadra from retained parents and full-area raw DEM; record output entities, threshold relationships, source coverage and runtime.
- [x] Exercise both role workflows and recommendation hard gates, including empty/unknown results, using controlled test weather.
- [x] Verify real provider lookup when available and clearly distinguish unavailable provider evidence from tested code paths.
- [x] Verify dataset activation, full geometry exports, responsive slope views, setup dependencies and recovery of the previous package.
- [x] Record an acceptance matrix for all eight phases with evidence and unresolved external-input limits; do not mark the full version complete if a required deliverable remains absent.

Status: approved parallel implementation delivered locally. All eight phases are implemented and verified; see docs/v1-acceptance.md for measured evidence and unresolved input limits. Reviewed changes are retained in the draft branch.
