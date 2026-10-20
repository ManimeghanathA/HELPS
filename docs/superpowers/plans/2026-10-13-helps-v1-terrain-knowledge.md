# HELPS V1 Terrain Knowledge Implementation Plan

Delivery status: implemented and verified locally; see `docs/v1-acceptance.md` for acceptance evidence and remaining external-input limits. The task instructions below are retained for reproducibility.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Populate a reproducible terrain→features→slope-zone→environment knowledgebase using the retained Bhadra candidates and real source evidence.

**Architecture:** A source-validation contract feeds metric DEM derivatives, per-terrain characterization and per-threshold child generation. A GeoPackage/SQLite repository persists the hierarchy and activates only explicitly selected, validated versions.

**Tech Stack:** Python 3.10+, NumPy, Rasterio, GeoPandas/Shapely, SQLite/GeoPackage.

**Spec:** `docs/superpowers/specs/2026-10-13-helps-v1-all-phases-design.md`.

## Global Constraints

- Preserve 2,484 source polygons and seven existing quarantines; retained parent map is 2,477 candidates.
- The 191 experiment is not the replacement.
- Thresholds `[0,2,4,6,8,10,12,15]` degrees; four-connected slope components.
- Approximately native 30 m metric DEM, float32 elevation, Horn 3×3 slope, detrended-plane RMS roughness, invalid neighborhoods withheld.
- Missing evidence is unknown; source hash/date/unit/coverage and analysis parameters are stored.
- Parent geometry and child-zone geometry remain separate; multiple threshold zones may legitimately overlap.
- All packages are staged, verified and explicitly activated; no latest-folder activation.

## Review Focus

- Small polygons with no DEM centres still receive area-weighted support accounting.
- Holes, multipart parents and threshold splitting remain intact.
- A cropped/invalid DEM or failed derivative cannot be treated as slope zero.
- Missing restriction/road/water/height coverage cannot become a fabricated unrestricted/accessible/clear result.
- Failed publication or activation preserves the previous selected package.

## Files and Contracts

Create `scripts/knowledge/{__init__,contracts,sources,dem,characterization,slope_zones,environment,repository,build}.py`.

`contracts.py` defines `SourceAsset`, `KnowledgeBuildSpec`, `TerrainRasterAssets`, `KnowledgeBuildResult` and JSON-serializable evidence states `measured`, `derived`, `unknown`, `invalid`. `KnowledgeBuildSpec` includes AOI/region/date, source paths, retained candidate seed, source metadata, restriction inputs and analysis parameters. `KnowledgeBuildResult` includes dataset ID, package/manifest paths, entity counts, validation and source-completeness report.

Primary feature keys: `terrain_id`, `source_zone_id`, `dataset_id`; child keys: `zone_id`, `terrain_id`, `slope_threshold_deg`. Geometry is metric inside processing and exported using the actual source CRS. Degree/metre/fraction units are explicit in field names.

### Task 1: Source Contract and Retained-Parent Import

**Files:** Create `contracts.py`, `sources.py`; test `tests/test_knowledge_sources.py`.

**Interfaces:** `validate_build_spec(spec: KnowledgeBuildSpec) -> dict`; `load_retained_terrain(spec) -> GeoDataFrame`; source checks return metadata and errors without mutating inputs.

- [ ] Write failing tests for full geometry/ID import, seven-quarantine policy, missing/invalid CRS, mismatched spectral/SCL grids, DEM units, source hash mismatch and missing restriction coverage.
- [ ] Run `python -m pytest tests/test_knowledge_sources.py -q`; observe meaningful failures.
- [ ] Implement explicit source modes: retained seed versus new candidate generation; validate bands/layers and finite coordinates; keep quality/completeness separate from file existence.
- [ ] Rerun tests; verify source files unchanged and retained geometry matches its stored baseline.
- [ ] Review and commit only this task's files.

### Task 2: Full-Area Metric DEM, Slope and Roughness

**Files:** Create `dem.py`; test `tests/test_dem_derivatives.py`.

**Interfaces:** `prepare_terrain_rasters(dem: SourceAsset, aoi: GeoDataFrame, output_dir: Path, resolution_m=30.0) -> TerrainRasterAssets`; pure `compute_derivatives(elevation, valid, dx_m, dy_m) -> tuple[slope_deg_array, roughness_m_array, derivative_valid_array]`.

The analytic test pins the algorithm independently of real source accuracy:

```python
def test_four_degree_plane_and_invalid_outer_edge():
    x = np.arange(5, dtype='float32') * 30.0
    elevation = np.tile(x * np.tan(np.deg2rad(4.0)), (5, 1))
    slope, roughness, valid = compute_derivatives(
        elevation, np.ones((5, 5), dtype=bool), 30.0, 30.0)
    assert valid[1:-1, 1:-1].all()
    assert not valid[0].any()
    assert np.allclose(slope[1:-1, 1:-1], 4.0, atol=1e-4)
    assert np.max(roughness[1:-1, 1:-1]) < 1e-4
```

- [ ] Write failing analytic tests: flat plane has zero slope/roughness; known X/Y plane yields expected angle; metre/foot declarations produce consistent derivatives; nodata contaminates the entire required neighborhood; old cropped coverage is reported; float32 reprojection preserves fractional elevations.
- [ ] Run the tests and observe failures.
- [ ] Reproject full AOI plus source-supported derivative halo; compute Horn degree slope and local detrended RMS. Write elevation/slope/roughness/valid rasters and manifest; no edge interpolation pretending missing support is observed.
- [ ] Rerun tests and inspect a full Bhadra coverage report using the approved raw source. Include FABDEM attribution/license and unresolved source metadata.
- [ ] Review and commit.

### Task 3: Per-Terrain Features with Support and Provenance

**Files:** Create `characterization.py`; test `tests/test_terrain_characterization.py`.

**Interfaces:** `characterize_terrain(terrain: GeoDataFrame, assets: TerrainRasterAssets, sources: dict, parameters: dict) -> DataFrame` keyed by `terrain_id`.

- [ ] Write failing tests for area-weighted sampling of a small no-centre polygon, mixed dated surface evidence, unknown/nodata fractions, elevation/slope summaries, vegetation indicators and preserved geometry.
- [ ] Run tests and observe failures.
- [ ] Implement raster-window sampling and area-weighted cell intersections. Store counts/support plus geometry metrics, class proportions, NDVI indicators, water indications, elevation/slope/roughness summaries. Distinguish raster surface indicators from verified firmness.
- [ ] Rerun tests; class fractions plus unknown coverage must reconcile with sampled coverage, and parent rows remain unchanged.
- [ ] Review and commit.

### Task 4: Multi-Threshold Connected Operational Zones

**Files:** Create `slope_zones.py`; reuse existing geometry/MIC helpers; test `tests/test_slope_zones.py`.

**Interfaces:** `generate_slope_zones(terrain, assets, exclusion_sources, thresholds=(0,2,4,6,8,10,12,15), parameters=None) -> tuple[GeoDataFrame,GeoDataFrame,DataFrame]` returning zones, centres and lineage/rejection records.

- [ ] Write failing tests for a known two-slope terrain split, corner-only adjacency, holes/multipart geometry, complete nodata, generic area/width/clearance gates and monotonic threshold coverage. Same-threshold children cannot overlap; cross-threshold nesting is expected.
- [ ] Run tests and observe failures.
- [ ] Threshold only valid native-scale slope cells, polygonize with four-connectivity, intersect parent/exclusions, split fragments and recompute geometry/MIC. Persist stable dataset-scoped IDs and parent/threshold links; record zero-child reasons.
- [ ] Rerun tests; verify child-within-parent, pixel/coverage/threshold checks and exact centre/boundary clearance.
- [ ] Review and commit.

### Task 5: Environmental Context

**Files:** Create `environment.py`; test `tests/test_zone_environment.py`.

**Interfaces:** `characterize_environment(zones, sources, analysis_radius_m=200.0) -> DataFrame` keyed by `zone_id`.

- [ ] Write failing tests for known road/water distance, incomplete road access tags, overlapping obstacle masks counted once, no mapped features versus missing source, and insufficient context coverage beyond AOI.
- [ ] Run tests and observe failures.
- [ ] Use spatial indexes for mapped proximity/counts and declared 200 m surrounding-area occupancy. Store access/connectivity evidence, water interaction, obstacle/vegetation fractions and relative 2D openness with coverage/height uncertainty.
- [ ] Rerun tests; no constant favourable openness or inferred hospital/road traversability values.
- [ ] Review and commit.

### Task 6: Persistent Hierarchy and Explicit Dataset Selection

**Files:** Create `repository.py`; test `tests/test_knowledge_repository.py`.

**Interfaces:** `write_package(build_data, output_path: Path) -> dict`; `validate_package(path: Path) -> dict`; `activate_dataset(dataset_id: str, registry_path: Path) -> dict`; `KnowledgeRepository(path)` exposes `list_terrain`, `get_terrain`, `list_zones`, `get_zone`, `query_zones` and `get_metadata`.

- [ ] Write failing tests for real parent-child foreign keys, duplicate IDs, corrupt geometry, absent referenced source, RTree lookup matching brute-force results, explicit AOI/version selection and failed activation retaining prior selection.
- [ ] Run tests and observe failures.
- [ ] Store GIS feature layers plus normalized AOI/run/source/characteristics/environment/lineage tables; create registered spatial indexes and threshold/parent indexes. Stage immutable packages and atomically update a verified registry pointer.
- [ ] Rerun tests; verify `PRAGMA foreign_key_check`, geometry/count consistency, source hashes and shared selected-version metadata.
- [ ] Review and commit.

### Task 7: Offline Build Orchestration and Bhadra Demonstration

**Files:** Create `build.py`; modify `scripts/pipeline/run_aoi_pipeline.py` only for explicit integration, preserving existing candidate-only commands; test `tests/test_knowledge_build.py`.

**Interfaces:** `build_knowledge(spec: KnowledgeBuildSpec, log=print) -> KnowledgeBuildResult`; CLI `python -m scripts.knowledge.build --spec <json>`. Publication/activation is a separate explicit action.

- [ ] Write failing synthetic end-to-end tests exercising all preceding modules, failed source/derivative phases, resumable stage manifests and a prior active package surviving failure.
- [ ] Run tests and observe failures.
- [ ] Orchestrate validated sources→retained/new terrain→derivatives→features→zones→environment→package; save stage logs, timings, coverage, audits and rejection reasons.
- [ ] Rerun tests, then build the full retained Bhadra dataset. Record parent/child/threshold counts, coverage, runtime and missing external evidence. Do not classify parent objects as failed merely because no compatible child exists.
- [ ] Review and commit. This package is the dependency for recommendation/UI integration.

## Exact Task Verification Commands

For each task, execute its command once against the new tests before implementation (expected meaningful failures), then after implementation (expected exit 0):

| Task | Command |
|---|---|
| 1 | `python -m pytest tests/test_knowledge_sources.py -q` |
| 2 | `python -m pytest tests/test_dem_derivatives.py -q` |
| 3 | `python -m pytest tests/test_terrain_characterization.py -q` |
| 4 | `python -m pytest tests/test_slope_zones.py -q` |
| 5 | `python -m pytest tests/test_zone_environment.py -q` |
| 6 | `python -m pytest tests/test_knowledge_repository.py -q` |
| 7 | `python -m pytest tests/test_knowledge_build.py -q` |
