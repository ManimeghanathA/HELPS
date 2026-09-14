import json

from scripts.search_historical_sentinel_dates import best_record_per_month


def test_best_record_per_month_keeps_lowest_cloud_scene():
    records = [
        {"date": "2025-10-12", "cloud_cover": 2.34, "product_id": "best"},
        {"date": "2025-10-21", "cloud_cover": 7.0, "product_id": "later"},
        {"date": "2025-12-11", "cloud_cover": 0.0, "product_id": "clear"},
    ]

    best = best_record_per_month(records)

    assert best == [
        {"month": "2025-10", "date": "2025-10-12", "cloud_cover": 2.34, "product_id": "best"},
        {"month": "2025-12", "date": "2025-12-11", "cloud_cover": 0.0, "product_id": "clear"},
    ]


def test_publish_bhadra_date_outputs_copies_raw_tiles_and_final_outputs(tmp_path, monkeypatch):
    from scripts.pipeline import historical_dates

    monkeypatch.setattr(historical_dates, "ROOT", tmp_path)
    run = tmp_path / "data" / "runs" / "run-1"
    run_archive = run / "archive"
    run_archive.mkdir(parents=True)
    inputs = tmp_path / "data" / "inputs" / "key" / "2025-10-12"
    tiles = inputs / "archive" / "tiles"
    tiles.mkdir(parents=True)
    (tiles / "0_0_spectral.tif").write_bytes(b"tile")
    (inputs / "spectral.tif").write_bytes(b"spectral")
    (inputs / "scl.tif").write_bytes(b"scl")
    (run_archive / "possible_open.tif").write_bytes(b"mask")
    for name in ["final_zones.gpkg", "final_zones.geojson", "final_zones.png", "summary.json", "run.json", "run.log"]:
        (run / name).write_text(name, encoding="utf-8")
    manifest = {"files": {"spectral": {"path": "data/inputs/key/2025-10-12/spectral.tif"},
                          "scl": {"path": "data/inputs/key/2025-10-12/scl.tif"}}}
    result = {"id": "run-1", "date": "2025-10-12", "provenance": manifest}

    published = historical_dates.publish_bhadra_date_outputs(result)

    raw = tmp_path / "data" / "raw" / "Sentinel2" / "2025-10-12"
    processed = tmp_path / "data" / "processed" / "Bhadra" / "sentinel2" / "2025-10-12"
    assert (raw / "tiles" / "0_0_spectral.tif").read_bytes() == b"tile"
    assert (raw / "spectral.tif").read_bytes() == b"spectral"
    assert (raw / "scl.tif").read_bytes() == b"scl"
    assert (processed / "bhadra_spectral.tif").read_bytes() == b"spectral"
    assert (processed / "bhadra_scl.tif").read_bytes() == b"scl"
    assert (processed / "bhadra_possible_open_mask.tif").read_bytes() == b"mask"
    assert (processed / "bhadra_final_open_land_zones.gpkg").read_text(encoding="utf-8") == "final_zones.gpkg"
    assert (processed / "bhadra_aoi_boundary.gpkg").exists()
    assert (processed / "bhadra_aoi_rgb_preview.png").exists()
    assert json.loads((processed / "published_from_run.json").read_text(encoding="utf-8"))["run_id"] == "run-1"
    assert published["raw_dir"] == str(raw)
    assert published["processed_dir"] == str(processed)


def test_run_bhadra_date_skips_published_date_unless_forced(tmp_path, monkeypatch):
    from scripts.pipeline import historical_dates

    monkeypatch.setattr(historical_dates, "ROOT", tmp_path)
    processed = tmp_path / "data" / "processed" / "Bhadra" / "sentinel2" / "2025-10-12"
    processed.mkdir(parents=True)
    (processed / "published_from_run.json").write_text('{"run_id":"old"}', encoding="utf-8")
    calls = []

    def fake_run(*args, **kwargs):
        calls.append(args)
        return {"id": "new", "date": "2025-10-12", "provenance": {"files": {}}}

    monkeypatch.setattr(historical_dates, "run", fake_run)

    skipped = historical_dates.run_bhadra_date("2025-10-12")

    assert skipped["status"] == "skipped"
    assert calls == []

    monkeypatch.setattr(historical_dates, "publish_bhadra_date_outputs", lambda result: {"date": result["date"]})
    forced = historical_dates.run_bhadra_date("2025-10-12", force=True)

    assert forced["id"] == "new"
    assert len(calls) == 1
