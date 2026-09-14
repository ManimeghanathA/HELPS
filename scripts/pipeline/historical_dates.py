"""Run Bhadra historical dates and publish them into date-based storage."""
import argparse
import json
import shutil
from pathlib import Path

import geopandas as gpd

from scripts.pipeline.inputs import ROOT, data_directory
from scripts.pipeline.run_aoi_pipeline import run

BHADRA_AOI = ROOT / "data" / "raw" / "Bhadra" / "bhadra_entire_region.geojson"
DEFAULT_DATES = ["2025-10-12", "2025-12-11", "2026-02-04", "2026-03-26", "2026-05-15"]


def copy_file(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def copy_tree_contents(source, destination):
    destination.mkdir(parents=True, exist_ok=True)
    if not source.exists():
        return
    for item in source.iterdir():
        target = destination / item.name
        if item.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(item, target)
        else:
            copy_file(item, target)


def published_paths(date):
    raw_dir = data_directory(ROOT / "data" / "raw" / "Sentinel2" / date)
    processed_dir = data_directory(ROOT / "data" / "processed" / "Bhadra" / "sentinel2" / date)
    return raw_dir, processed_dir


def already_published(date):
    _, processed_dir = published_paths(date)
    return (processed_dir / "published_from_run.json").exists()


def export_aoi_assets(run_dir, processed_dir, spectral):
    aoi_path = run_dir / "aoi.geojson"
    if aoi_path.exists():
        aoi = gpd.read_file(aoi_path)
        aoi.to_file(processed_dir / "bhadra_aoi_boundary.gpkg", layer="aoi_boundary", driver="GPKG")
    else:
        (processed_dir / "bhadra_aoi_boundary.gpkg").touch()
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
        import rasterio
        from rasterio.plot import plotting_extent

        with rasterio.open(spectral) as src:
            scale = min(1, 1600 / max(src.width, src.height))
            rgb = src.read([3, 2, 1], out_shape=(3, max(1, int(src.height * scale)), max(1, int(src.width * scale))))
            extent, crs = plotting_extent(src), src.crs
        rgb = np.moveaxis(rgb, 0, -1)
        rgb = np.clip(np.nan_to_num(rgb) / .3, 0, 1)
        fig, ax = plt.subplots(figsize=(10, 10), facecolor="#121918")
        ax.imshow(rgb, extent=extent)
        if aoi_path.exists():
            aoi.to_crs(crs).boundary.plot(ax=ax, color="white", linewidth=1.0)
        ax.set_xlim(extent[:2])
        ax.set_ylim(extent[2:])
        ax.set_axis_off()
        fig.savefig(processed_dir / "bhadra_aoi_rgb_preview.png", dpi=160, bbox_inches="tight", pad_inches=0)
        plt.close(fig)
    except Exception:
        (processed_dir / "bhadra_aoi_rgb_preview.png").touch()


def publish_bhadra_date_outputs(result):
    date = result["date"]
    raw_dir, processed_dir = published_paths(date)
    run_dir = ROOT / "data" / "runs" / result["id"]
    provenance = result.get("provenance", {})
    files = provenance.get("files", {})
    spectral = ROOT / files["spectral"]["path"]
    scl = ROOT / files["scl"]["path"]
    input_dir = spectral.parent
    copy_tree_contents(input_dir / "archive" / "tiles", raw_dir / "tiles")
    copy_file(spectral, raw_dir / "spectral.tif")
    copy_file(scl, raw_dir / "scl.tif")
    copy_file(spectral, processed_dir / "bhadra_spectral.tif")
    copy_file(scl, processed_dir / "bhadra_scl.tif")
    export_aoi_assets(run_dir, processed_dir, spectral)
    copies = {
        "archive/possible_open.tif": "bhadra_possible_open_mask.tif",
        "final_zones.gpkg": "bhadra_final_open_land_zones.gpkg",
        "final_zones.geojson": "bhadra_final_open_land_zones.geojson",
        "final_zones.png": "bhadra_final_open_land_zones.png",
        "summary.json": "summary.json",
        "run.json": "run.json",
        "run.log": "run.log",
    }
    for source_name, target_name in copies.items():
        source = run_dir / source_name
        if source.exists():
            copy_file(source, processed_dir / target_name)
    manifest = {
        "date": date,
        "run_id": result["id"],
        "raw_dir": str(raw_dir),
        "processed_dir": str(processed_dir),
    }
    (processed_dir / "published_from_run.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def run_bhadra_date(date, log=print, run_tests=True, force=False):
    if already_published(date) and not force:
        raw_dir, processed_dir = published_paths(date)
        return {
            "date": date,
            "status": "skipped",
            "reason": "already_published",
            "published": {
                "date": date,
                "raw_dir": str(raw_dir),
                "processed_dir": str(processed_dir),
            },
        }
    result = run(BHADRA_AOI, date, "Bhadra", log=log, run_tests=run_tests)
    result["published"] = publish_bhadra_date_outputs(result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dates", nargs="*", default=DEFAULT_DATES)
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    results = []
    for date in args.dates:
        results.append(run_bhadra_date(date, run_tests=not args.skip_tests, force=args.force))
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
