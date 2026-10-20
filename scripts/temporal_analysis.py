"""Temporal comparison and candidate database utilities for Bhadra."""
import argparse
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import geometry_mask, rasterize

from scripts.pipeline.inputs import ROOT
from scripts.processing.open_land_detector import NOT_OPEN, POSSIBLE_OPEN, UNKNOWN


def default_history_path():
    return ROOT / "data" / "processed" / "Bhadra" / "sentinel2" / "history_dates.json"


def load_history_dates(path=None):
    path = Path(path) if path is not None else default_history_path()
    data = json.loads(path.read_text(encoding="utf-8"))
    return list(data["history_dates"])


def sentinel2_date_dir(date):
    return ROOT / "data" / "processed" / "Bhadra" / "sentinel2" / date


def final_zones_path(date):
    return sentinel2_date_dir(date) / "bhadra_final_open_land_zones.gpkg"


def possible_open_mask_path(date):
    folder = sentinel2_date_dir(date)
    for name in ["bhadra_possible_open_mask.tif", "bhadra_possible_open_mask_v2.tif"]:
        path = folder / name
        if path.exists():
            return path
    raise FileNotFoundError(f"No possible-open mask found for {date} in {folder}")


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
    temporal_support = 0.0 if support_denominator == 0 else min(1.0, total_valid / support_denominator)
    return {
        "temporal_open_confidence": None if total_valid == 0 else total_open / total_valid,
        "temporal_support": temporal_support,
        "valid_history_count": valid_history_count,
    }


def measure_candidate_against_state(candidate_geometry, state_path):
    with rasterio.open(state_path) as src:
        state = src.read(1)
        pixel_area_m2 = abs(src.transform.a * src.transform.e)
        transform = src.transform
    return measure_candidate_against_array(candidate_geometry, state, transform, pixel_area_m2)


def measure_candidate_against_array(candidate_geometry, state, transform, pixel_area_m2):
    inside = geometry_mask(
        [candidate_geometry],
        out_shape=state.shape,
        transform=transform,
        invert=True,
    )
    open_pixels = int(np.count_nonzero(inside & (state == POSSIBLE_OPEN)))
    unknown_pixels = int(np.count_nonzero(inside & (state == UNKNOWN)))
    not_open_pixels = int(np.count_nonzero(inside & (state == NOT_OPEN)))
    open_area = open_pixels * pixel_area_m2
    not_open_area = not_open_pixels * pixel_area_m2
    unknown_area = unknown_pixels * pixel_area_m2
    return {
        "open_area_m2": float(open_area),
        "not_open_area_m2": float(not_open_area),
        "unknown_area_m2": float(unknown_area),
        "valid_area_m2": float(open_area + not_open_area),
    }


def measure_candidates_against_state(candidate_geometries, state_path):
    with rasterio.open(state_path) as src:
        state = src.read(1)
        pixel_area_m2 = abs(src.transform.a * src.transform.e)
        transform = src.transform
    return [
        measure_candidate_against_array(geometry, state, transform, pixel_area_m2)
        for geometry in candidate_geometries
    ]


def measure_candidates_against_state_by_label(candidates, state_path):
    with rasterio.open(state_path) as src:
        state = src.read(1)
        transform = src.transform
        pixel_area_m2 = abs(src.transform.a * src.transform.e)
    labels = rasterize(
        ((geometry, index) for index, geometry in enumerate(candidates.geometry, start=1)),
        out_shape=state.shape,
        transform=transform,
        fill=0,
        dtype="int32",
    )
    candidate_count = len(candidates)
    valid_labels = labels.ravel()
    state_values = state.ravel()
    open_counts = np.bincount(
        valid_labels[state_values == POSSIBLE_OPEN],
        minlength=candidate_count + 1,
    )
    unknown_counts = np.bincount(
        valid_labels[state_values == UNKNOWN],
        minlength=candidate_count + 1,
    )
    not_open_counts = np.bincount(
        valid_labels[state_values == NOT_OPEN],
        minlength=candidate_count + 1,
    )
    results = []
    for index in range(1, candidate_count + 1):
        open_area = float(open_counts[index] * pixel_area_m2)
        not_open_area = float(not_open_counts[index] * pixel_area_m2)
        unknown_area = float(unknown_counts[index] * pixel_area_m2)
        results.append(
            {
                "open_area_m2": open_area,
                "not_open_area_m2": not_open_area,
                "unknown_area_m2": unknown_area,
                "valid_area_m2": open_area + not_open_area,
            }
        )
    return results


def build_candidate_database(current_date, history_dates, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    candidates = gpd.read_file(final_zones_path(current_date), layer="final_open_land_zones")
    evidence_by_history = [
        measure_candidates_against_state_by_label(candidates, possible_open_mask_path(history_date))
        for history_date in history_dates
    ]
    scored_rows = []
    for candidate_index, (_, row) in enumerate(candidates.iterrows()):
        evidence = [
            history_evidence[candidate_index]
            for history_evidence in evidence_by_history
        ]
        aggregate = aggregate_temporal_evidence(
            candidate_area_m2=float(row["area_m2"]),
            history_date_count=len(history_dates),
            rows=evidence,
        )
        scored = row.to_dict()
        scored.update(aggregate)
        scored["history_dates_used"] = ",".join(history_dates)
        scored_rows.append(scored)
    scored_gdf = gpd.GeoDataFrame(scored_rows, geometry="geometry", crs=candidates.crs)
    scored_gdf.to_file(output_dir / "candidates.gpkg", layer="candidates", driver="GPKG")
    (output_dir / "candidates.geojson").write_text(scored_gdf.to_crs(4326).to_json(), encoding="utf-8")
    scored_gdf.drop(columns="geometry").to_csv(output_dir / "candidates.csv", index=False)
    metadata = {
        "current_date": current_date,
        "history_dates": list(history_dates),
        "candidate_count": int(len(scored_gdf)),
    }
    (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def default_output_dir(current_date):
    return ROOT / "data" / "processed" / "Bhadra" / "candidate_database" / current_date


def main(argv=None, builder=build_candidate_database):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--current-date", required=True)
    parser.add_argument("--history", default=str(default_history_path()))
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    output = Path(args.output) if args.output else default_output_dir(args.current_date)
    result = builder(args.current_date, load_history_dates(args.history), output)
    if argv is None:
        print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    main()
