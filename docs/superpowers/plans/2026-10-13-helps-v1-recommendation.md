# HELPS V1 Recommendation Implementation Plan

Delivery status: implemented and verified locally; see `docs/v1-acceptance.md` for acceptance evidence and remaining external-input limits. The task instructions below are retained for reproducibility.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evaluate stored measured zones with mandatory compatibility/footprint checks and return explained, deterministic mission rankings.

**Architecture:** An immutable selected knowledge snapshot supplies indexed candidates. Separate input, weather, compatibility, footprint and ranking modules produce pass/fail/unknown evidence before result generation.

**Tech Stack:** Python, existing weather module, SQLite/GeoPackage repository, Shapely, Flask.

**Spec:** `docs/superpowers/specs/2026-10-13-helps-v1-all-phases-design.md`; repository contract in `2026-10-13-helps-v1-terrain-knowledge.md`.

## Global Constraints

- Preserve parent candidate browsing; recommendation eligibility applies to measured child zones.
- Missing mandatory evidence is unknown, never favourable.
- Scores rank survivors and are not safety probabilities.
- Thresholds `[0,2,4,6,8,10,12,15]` are research analysis thresholds; built-in profile limits remain identified research configuration until verified.
- Exact metric footprint checks preserve holes and multipart boundaries.
- Selected dataset, profile, mission and weather identities travel with every result.

## Review Focus

- Overslope/undersized zones cannot rank well enough to bypass gates.
- Missing/stale/historical weather retains its true evidence state and dates.
- Invalid custom profiles, unknown IDs and inconsistent rotor/clearance values yield input errors.
- Nearby nested threshold zones do not flood top-K with duplicate opportunities.
- Failed reloads and requests for another dataset cannot mix geometry and metadata.

## Files and Contracts

Create `scripts/recommendation/{__init__,contracts,inputs,weather_policy,compatibility,ranking,engine}.py`. Modify `helicopter_profiles.py`, `landing_zone_engine.py`, `app.py`; add focused tests. Keep existing distance/bearing helpers and weather acquisition.

`RecommendationRequest` includes dataset/region, query coordinates, profile/overrides, mission, UTC target time, radius, top-K and declared evidence policy. `GateDecision` contains `state: pass|fail|unknown`, reason codes and evidence. `RecommendationResult` contains request/dataset identity, candidate/gate counts, eligible spots, uncertain/excluded reasons and source limits.

### Task 1: Validated Inputs and Versioned Profiles

**Files:** Create `contracts.py`, `inputs.py`; modify `helicopter_profiles.py`; test `tests/test_recommendation_inputs.py`.

- [ ] Write failing tests for NaN/Infinity, bounds/radius/top-K, unknown model/mission IDs, invalid dates, nonnumeric/negative overrides and inconsistent clearance versus aircraft dimensions.
- [ ] Run tests and observe failures.
- [ ] Implement `validate_request(payload: dict) -> RecommendationRequest` and `resolve_profile(model_id, overrides) -> dict`; expose configuration source/revision and research status. Reject silent fallbacks.
- [ ] Rerun tests; valid existing profiles/mission IDs still resolve with documented semantics.
- [ ] Review and commit.

### Task 2: Weather Feasibility and Coverage-Aware Reuse

**Files:** Create `weather_policy.py`; reuse `weather_pipeline.py`; test `tests/test_weather_policy.py`.

**Interfaces:** `assess_weather(snapshot, profile, requested_at, policy, heading_deg=None) -> GateDecision`; `WeatherSnapshotCache.get_or_fetch(location, requested_at, coverage_policy) -> dict`.

- [ ] Write failing tests for missing/null wind/visibility/rain, stale retrieval, historical versus current validity, configured-limit violations, cached time/location coverage and unknown heading/crosswind assessment. Wind-from 270° must not be mislabeled as an into-wind 090° heading.
- [ ] Run tests and observe failures.
- [ ] Implement strict snapshot validation, bounded/time-and-area-scoped reuse, provenance labels for client-supplied values and configured hard-limit decisions. Never convert absent wind to calm weather.
- [ ] Rerun tests with controlled provider fixtures and failure paths; record actual provider availability separately.
- [ ] Review and commit.

### Task 3: Mandatory Terrain and Exact Footprint Checks

**Files:** Create `compatibility.py`; test `tests/test_compatibility_gates.py`.

**Interfaces:** `assess_zone(zone_record, terrain_record, environment_record, profile, weather_decision, policy) -> dict`; `validate_footprint(metric_geometry, metric_poi, required_radius_m) -> GateDecision`.

The footprint regression must detect a hole even with a sufficient outer bounding box:

```python
def test_required_circle_crosses_excluded_interior():
    outer = box(-20, -20, 20, 20)
    hole = box(8, -2, 9, 2)
    geometry = Polygon(outer.exterior.coords, [hole.exterior.coords])
    decision = validate_footprint(geometry, Point(0, 0), 10.0)
    assert decision.state == 'fail'
```

- [ ] Write failing tests for 30° slope versus 10° limit, deficient area/diameter, nodata slope, unsupported surface/restrictions, centre inside a hole, a circle crossing a hole/boundary and multiple disconnected parts.
- [ ] Run tests and observe failures.
- [ ] Apply independent pass/fail/unknown gates; test centre containment and actual boundary distance plus metric footprint containment. Geometry tolerance cannot hide a real shortfall. Unknown required policy cannot be labelled fully compatible.
- [ ] Rerun tests; verify weighted scores are never consulted by mandatory gates.
- [ ] Review and commit.

### Task 4: Context-Based Mission Ranking and Nested-Zone Deduplication

**Files:** Create `ranking.py`; test `tests/test_mission_ranking.py`.

**Interfaces:** `rank_eligible(assessed_zones, mission, query_location, top_k) -> list[dict]`.

- [ ] Write failing tests for access-driven medevac ordering, distance-driven urgency/fuel ordering, missing optional factor normalization, stable ties, nearby same-opportunity threshold duplicates and preservation of distinct disconnected opportunities.
- [ ] Run tests and observe failures.
- [ ] Rank passing zones using stored features and declared mission weights. Emit factors/contributions and straight-line ETA assumptions. Suppress nested duplicates using parent identity, footprint/geometry overlap and reference-point distance; do not collapse every child of a parent indiscriminately.
- [ ] Rerun tests; no failed/unknown mandatory zone reaches eligible top-K.
- [ ] Review and commit.

### Task 5: Snapshot Engine and API Integration

**Files:** Create `engine.py`; modify `landing_zone_engine.py`, `app.py`; test `tests/test_recommendation_api.py`.

**Interfaces:** `RecommendationEngine(repository, weather_service).recommend(request) -> RecommendationResult`; explicit selected-repository reload builds then swaps a validated snapshot. API `POST /api/recommendations` consumes the request contract.

- [ ] Write failing integration tests for indexed radius retrieval, empty/incompatible/unknown results, exact result geometry/source identity, invalid input errors and failed activation/reload keeping the prior snapshot.
- [ ] Run tests and observe failures.
- [ ] Connect repository→weather feasibility→compatible threshold selection→zone/footprint gates→ranking→explanations. Remove fabricated slope/surface and favourable missing-weather defaults from the V1 path. Legacy endpoints are documented separately, not used to claim full-V1 recommendations.
- [ ] Rerun tests and compare indexed queries against brute force; benchmark query/rank latency with provider time measured separately.
- [ ] Review and commit. Provide response fixtures for the role-workspace plan.

## Exact Task Verification Commands

Run before implementation to establish meaningful failures and again afterwards expecting exit 0:

| Task | Command |
|---|---|
| 1 | `python -m pytest tests/test_recommendation_inputs.py -q` |
| 2 | `python -m pytest tests/test_weather_policy.py -q` |
| 3 | `python -m pytest tests/test_compatibility_gates.py -q` |
| 4 | `python -m pytest tests/test_mission_ranking.py -q` |
| 5 | `python -m pytest tests/test_recommendation_api.py -q` |
