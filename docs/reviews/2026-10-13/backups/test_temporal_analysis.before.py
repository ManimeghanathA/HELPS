import numpy as np
import geopandas as gpd
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box

import scripts.temporal_analysis as temporal_analysis
from scripts.temporal_analysis import (
    aggregate_temporal_evidence,
    build_candidate_database,
    load_history_dates,
    main,
    measure_candidates_against_state_by_label,
    measure_candidates_against_state,
    measure_candidate_against_state,
)


def test_load_history_dates_reads_ordered_dates(tmp_path):
    registry = tmp_path / "history_dates.json"
    registry.write_text(
        '{"aoi":"Bhadra","history_dates":["2025-10-12","2025-12-11"],"max_history_dates":5}',
        encoding="utf-8",
    )

    assert load_history_dates(registry) == ["2025-10-12", "2025-12-11"]


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


def test_aggregate_temporal_support_is_capped_at_one():
    result = aggregate_temporal_evidence(
        candidate_area_m2=90.0,
        history_date_count=1,
        rows=[
            {"open_area_m2": 100.0, "not_open_area_m2": 0.0, "unknown_area_m2": 0.0},
        ],
    )

    assert result["temporal_support"] == 1.0


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


def test_measure_candidates_against_state_reuses_one_raster_read(tmp_path):
    state_path = tmp_path / "state.tif"
    state = np.array(
        [
            [1, 2],
            [255, 1],
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

    results = measure_candidates_against_state([box(0, 0, 10, 20), box(10, 0, 20, 20)], state_path)

    assert results == [
        {"open_area_m2": 100.0, "not_open_area_m2": 0.0, "unknown_area_m2": 100.0, "valid_area_m2": 100.0},
        {"open_area_m2": 100.0, "not_open_area_m2": 100.0, "unknown_area_m2": 0.0, "valid_area_m2": 200.0},
    ]


def test_measure_candidates_against_state_by_label_counts_all_candidates_in_one_pass(tmp_path):
    state_path = tmp_path / "state.tif"
    state = np.array(
        [
            [1, 2],
            [255, 1],
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
    candidates = gpd.GeoDataFrame(
        [{"geometry": box(0, 0, 10, 20)}, {"geometry": box(10, 0, 20, 20)}],
        geometry="geometry",
        crs=32643,
    )

    results = measure_candidates_against_state_by_label(candidates, state_path)

    assert results == [
        {"open_area_m2": 100.0, "not_open_area_m2": 0.0, "unknown_area_m2": 100.0, "valid_area_m2": 100.0},
        {"open_area_m2": 100.0, "not_open_area_m2": 100.0, "unknown_area_m2": 0.0, "valid_area_m2": 200.0},
    ]


def test_build_candidate_database_writes_expected_schema(tmp_path, monkeypatch):
    monkeypatch.setattr(temporal_analysis, "ROOT", tmp_path)
    current = tmp_path / "data" / "processed" / "Bhadra" / "sentinel2" / "2026-06-01"
    history = tmp_path / "data" / "processed" / "Bhadra" / "sentinel2" / "2025-10-12"
    current.mkdir(parents=True)
    history.mkdir(parents=True)
    candidate = gpd.GeoDataFrame(
        [
            {
                "zone_id": "Bhadra_ZONE_000001",
                "area_m2": 400.0,
                "length_m": 20.0,
                "width_m": 20.0,
                "max_clear_diameter_m": 20.0,
                "max_clear_radius_m": 10.0,
                "geometry": box(0, 0, 20, 20),
            }
        ],
        geometry="geometry",
        crs=32643,
    )
    candidate.to_file(current / "bhadra_final_open_land_zones.gpkg", layer="final_open_land_zones", driver="GPKG")
    state = np.array([[1, 1], [2, 255]], dtype="uint8")
    with rasterio.open(
        history / "bhadra_possible_open_mask.tif",
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

    output = tmp_path / "out"
    result = build_candidate_database("2026-06-01", ["2025-10-12"], output)

    assert result["candidate_count"] == 1
    written = gpd.read_file(output / "candidates.gpkg", layer="candidates")
    expected_columns = {
        "zone_id",
        "geometry",
        "area_m2",
        "length_m",
        "width_m",
        "max_clear_diameter_m",
        "max_clear_radius_m",
        "temporal_open_confidence",
        "temporal_support",
        "valid_history_count",
        "history_dates_used",
    }
    assert expected_columns.issubset(set(written.columns))
    assert written.loc[0, "temporal_open_confidence"] == 200.0 / 300.0
    assert written.loc[0, "temporal_support"] == 300.0 / 400.0
    assert (output / "candidates.geojson").exists()
    assert (output / "candidates.csv").exists()
    assert (output / "metadata.json").exists()


def test_main_uses_supplied_current_date_history_and_output(tmp_path, monkeypatch):
    history = tmp_path / "history_dates.json"
    history.write_text(
        '{"history_dates":["2025-10-12","2025-12-11"]}',
        encoding="utf-8",
    )
    output = tmp_path / "db"
    calls = []

    def fake_builder(current_date, history_dates, output_dir):
        calls.append((current_date, history_dates, output_dir))
        return {"candidate_count": 3}

    result = main(
        [
            "--current-date",
            "2026-06-01",
            "--history",
            str(history),
            "--output",
            str(output),
        ],
        builder=fake_builder,
    )

    assert result == {"candidate_count": 3}
    assert calls == [("2026-06-01", ["2025-10-12", "2025-12-11"], output)]
