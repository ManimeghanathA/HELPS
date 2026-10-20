# Temporal Candidate Database Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the June 1 temporal scoring pipeline and first candidate feature database using the five processed Bhadra history dates.

**Architecture:** Keep temporal comparison independent from the single-date Sentinel processing pipeline. Current-date candidate polygons are the records we score; historical date rasters are evidence layers. The final candidate database stores only aggregate temporal fields, not permanent per-date temporal rows.

**Tech Stack:** Python, GeoPandas, Rasterio, Shapely, NumPy, Pytest, GeoPackage/GeoJSON/CSV outputs.

**Spec:** ChatGPT planning thread `HELPS_PHASE_1_2`, latest temporal/database discussion.

## Global Constraints

- Current/base date is `2026-06-01`.
- Initial history dates are `2025-10-12`, `2025-12-11`, `2026-02-04`, `2026-03-26`, `2026-05-15`.
- Historical UNKNOWN/cloud evidence must not count as rejection.
- Temporal confidence is `sum(open_area_m2) / sum(valid_area_m2)`.
- Temporal support is `sum(valid_area_m2) / (history_date_count * candidate_area_m2)`.
- If total valid history area is zero, temporal confidence must be null, not zero.
- The final candidate database stores aggregate temporal fields only.
- Slope zones are a later linked-table task and must not be mixed into the first temporal database implementation.

---

## File Structure

- Create `data/processed/Bhadra/sentinel2/history_dates.json`: source of truth for accepted history dates.
- Create `scripts/temporal_analysis.py`: independent temporal comparison and candidate database CLI.
- Create `tests/test_temporal_analysis.py`: unit tests for history loading, raster area accounting, aggregation, and output schema.
- Modify `README.md`: document temporal analysis usage and database outputs after implementation.

---

### Task 1: History Registry

**Files:**
- Create: `data/processed/Bhadra/sentinel2/history_dates.json`
- Create: `tests/test_temporal_analysis.py`
- Create: `scripts/temporal_analysis.py`

**Interfaces:**
- Produces: `load_history_dates(path: Path) -> list[str]`
- Produces: `default_history_path() -> Path`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

from scripts.temporal_analysis import load_history_dates


def test_load_history_dates_reads_ordered_dates(tmp_path):
    registry = tmp_path / "history_dates.json"
    registry.write_text(
        '{"aoi":"Bhadra","history_dates":["2025-10-12","2025-12-11"],"max_history_dates":5}',
        encoding="utf-8",
    )

    assert load_history_dates(registry) == ["2025-10-12", "2025-12-11"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `helps_env\Scripts\python.exe -m pytest tests\test_temporal_analysis.py::test_load_history_dates_reads_ordered_dates -q`

Expected: FAIL because `scripts.temporal_analysis` does not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
import json
from pathlib import Path

from scripts.pipeline.inputs import ROOT


def default_history_path():
    return ROOT / "data" / "processed" / "Bhadra" / "sentinel2" / "history_dates.json"


def load_history_dates(path=None):
    path = Path(path) if path is not None else default_history_path()
    data = json.loads(path.read_text(encoding="utf-8"))
    return list(data["history_dates"])
```

- [ ] **Step 4: Add the registry file**

Create `data/processed/Bhadra/sentinel2/history_dates.json`:

```json
{
  "aoi": "Bhadra",
  "history_dates": [
    "2025-10-12",
    "2025-12-11",
    "2026-02-04",
    "2026-03-26",
    "2026-05-15"
  ],
  "max_history_dates": 5,
  "current_reference_date": "2026-06-01"
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `helps_env\Scripts\python.exe -m pytest tests\test_temporal_analysis.py::test_load_history_dates_reads_ordered_dates -q`

Expected: PASS.

---

### Task 2: Temporal Formula Aggregation

**Files:**
- Modify: `scripts/temporal_analysis.py`
- Modify: `tests/test_temporal_analysis.py`

**Interfaces:**
- Produces: `aggregate_temporal_evidence(candidate_area_m2: float, history_date_count: int, rows: list[dict]) -> dict`

- [ ] **Step 1: Write the failing tests**

```python
from scripts.temporal_analysis import aggregate_temporal_evidence


def test_aggregate_temporal_evidence_excludes_unknown_area():
    result = aggregate_temporal_evidence(
        candidate_area_m2=100.0,
        history_date_count=2,
        rows=[
            {"open_area_m2": 80.0, "not_open_area_m2": 10.0, "unknown_area_m2": 10.0},
            {"open_area_m2": 20.0, "not_open_area_m2": 30.0, "unknown_area_m2": 50.0},
        ],
    )

    assert result["temporal_open_confidence"] == 100.0 / 140.0
    assert result["temporal_support"] == 140.0 / 200.0
    assert result["valid_history_count"] == 2


def test_aggregate_temporal_evidence_returns_null_confidence_when_no_valid_area():
    result = aggregate_temporal_evidence(
        candidate_area_m2=100.0,
        history_date_count=2,
        rows=[
            {"open_area_m2": 0.0, "not_open_area_m2": 0.0, "unknown_area_m2": 100.0},
        ],
    )

    assert result["temporal_open_confidence"] is None
    assert result["temporal_support"] == 0.0
    assert result["valid_history_count"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `helps_env\Scripts\python.exe -m pytest tests\test_temporal_analysis.py -q`

Expected: FAIL because `aggregate_temporal_evidence` is missing.

- [ ] **Step 3: Implement aggregation**

```python
def aggregate_temporal_evidence(candidate_area_m2, history_date_count, rows):
    total_open = sum(float(row["open_area_m2"]) for row in rows)
    total_not_open = sum(float(row["not_open_area_m2"]) for row in rows)
    total_valid = total_open + total_not_open
    valid_history_count = sum(
        1
        for row in rows
        if float(row["open_area_m2"]) + float(row["not_open_area_m2"]) > 0
    )
    support_denominator = float(history_date_count) * float(candidate_area_m2)
    return {
        "temporal_open_confidence": None if total_valid == 0 else total_open / total_valid,
        "temporal_support": 0.0 if support_denominator == 0 else total_valid / support_denominator,
        "valid_history_count": valid_history_count,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `helps_env\Scripts\python.exe -m pytest tests\test_temporal_analysis.py -q`

Expected: PASS.

---

### Task 3: Raster Evidence For One Candidate And One Date

**Files:**
- Modify: `scripts/temporal_analysis.py`
- Modify: `tests/test_temporal_analysis.py`

**Interfaces:**
- Produces: `measure_candidate_against_state(candidate_geometry, state_path: Path) -> dict`

- [ ] **Step 1: Write synthetic raster test**

```python
import geopandas as gpd
import numpy as np
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box

from scripts.temporal_analysis import measure_candidate_against_state


def test_measure_candidate_against_state_counts_open_not_open_and_unknown(tmp_path):
    state_path = tmp_path / "state.tif"
    state = np.array(
        [
            [1, 1],
            [2, 255],
        ],
        dtype="uint8",
    )
    with rasterio.open(
        state_path,
        "w",
        driver="GTiff",
        width=2,
        height=2,
        count=1,
        dtype="uint8",
        transform=from_origin(0, 20, 10, 10),
        crs=32643,
    ) as dst:
        dst.write(state, 1)

    result = measure_candidate_against_state(box(0, 0, 20, 20), state_path)

    assert result["open_area_m2"] == 200.0
    assert result["not_open_area_m2"] == 100.0
    assert result["unknown_area_m2"] == 100.0
    assert result["valid_area_m2"] == 300.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `helps_env\Scripts\python.exe -m pytest tests\test_temporal_analysis.py::test_measure_candidate_against_state_counts_open_not_open_and_unknown -q`

Expected: FAIL because function is missing.

- [ ] **Step 3: Implement raster measurement**

Implementation rule:
- Treat state `1` as OPEN.
- Treat state `255` as UNKNOWN.
- Treat all other nonzero values as NOT_OPEN.
- Pixel area is `abs(transform.a * transform.e)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `helps_env\Scripts\python.exe -m pytest tests\test_temporal_analysis.py::test_measure_candidate_against_state_counts_open_not_open_and_unknown -q`

Expected: PASS.

---

### Task 4: Build Candidate Database For June 1

**Files:**
- Modify: `scripts/temporal_analysis.py`
- Modify: `tests/test_temporal_analysis.py`

**Interfaces:**
- Produces: `build_candidate_database(current_date: str, history_dates: list[str], output_dir: Path) -> dict`

- [ ] **Step 1: Write output schema test**

Use tiny GeoPackage/raster fixtures in `tmp_path`. The test must assert that the output candidate rows contain:

```text
zone_id
geometry
area_m2
length_m
width_m
max_clear_diameter_m
max_clear_radius_m
temporal_open_confidence
temporal_support
valid_history_count
history_dates_used
```

- [ ] **Step 2: Run schema test to verify it fails**

Run: `helps_env\Scripts\python.exe -m pytest tests\test_temporal_analysis.py -q`

Expected: FAIL because database builder is missing.

- [ ] **Step 3: Implement builder**

Implementation outputs:

```text
data/processed/Bhadra/candidate_database/<current_date>/
  candidates.gpkg
  candidates.geojson
  candidates.csv
  metadata.json
```

- [ ] **Step 4: Run schema test to verify it passes**

Run: `helps_env\Scripts\python.exe -m pytest tests\test_temporal_analysis.py -q`

Expected: PASS.

---

### Task 5: CLI And README

**Files:**
- Modify: `scripts/temporal_analysis.py`
- Modify: `README.md`
- Modify: `tests/test_temporal_analysis.py`

**Interfaces:**
- Produces CLI: `python -m scripts.temporal_analysis --current-date 2026-06-01`

- [ ] **Step 1: Add CLI test for argument parsing**

Test that `main(["--current-date", "2026-06-01", "--history", "history_dates.json"])` calls the builder with the supplied date and history list.

- [ ] **Step 2: Run CLI test to verify it fails**

Run: `helps_env\Scripts\python.exe -m pytest tests\test_temporal_analysis.py -q`

Expected: FAIL because CLI is missing.

- [ ] **Step 3: Implement CLI**

Required arguments:

```text
--current-date YYYY-MM-DD
--history optional path, default data/processed/Bhadra/sentinel2/history_dates.json
--output optional path, default data/processed/Bhadra/candidate_database/<current-date>
```

- [ ] **Step 4: Document usage**

Add README section:

```powershell
python -m scripts.temporal_analysis --current-date 2026-06-01
```

- [ ] **Step 5: Run full verification**

Run:

```powershell
helps_env\Scripts\python.exe -m pytest tests -q
helps_env\Scripts\python.exe -m scripts.temporal_analysis --current-date 2026-06-01
```

Expected:
- Tests pass.
- Candidate database is written under `data/processed/Bhadra/candidate_database/2026-06-01/`.

---

## Execution Checklist

- [ ] Task 1 complete: history registry exists and loads.
- [ ] Task 2 complete: temporal formula aggregation tested.
- [ ] Task 3 complete: one-candidate raster evidence tested.
- [ ] Task 4 complete: June 1 candidate database generated.
- [ ] Task 5 complete: CLI and README documented.
- [ ] Full test suite passes.
- [ ] June 1 candidate database visually/sample-checked.
- [ ] Commit and push.

## Self-Review

- Spec coverage: Covers history registry, temporal computation, candidate-level aggregate storage, first candidate feature database, and CLI.
- Placeholder scan: No placeholder implementation steps; unresolved slope work is explicitly out of scope for this plan.
- Type consistency: `history_dates`, `temporal_open_confidence`, `temporal_support`, and `valid_history_count` names are consistent across tasks.
