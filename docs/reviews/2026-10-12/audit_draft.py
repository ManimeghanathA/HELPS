"""Read-only evidence collection for Neha_branch; writes review artifacts only.

Run from HELPSs: helps_env/Scripts/python.exe docs/reviews/2026-10-12/audit_draft.py
"""
import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import rasterize
from shapely.geometry import Polygon

ROOT = Path(__file__).resolve().parents[3]
DRAFT = ROOT / "HELPS - draft"
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(DRAFT))

from landing_zone_engine import LandingZoneEngine
from scripts.processing.open_land_detector import (
    _read_inputs, safe_normalized_difference, classify_open_pixels, apply_cloud_edge_buffer,
)


def main():
    base = DRAFT / "data/processed/Bhadra"
    imagery = base / "sentinel2/2026-06-01"
    zones = gpd.read_file(imagery / "bhadra_final_open_land_zones.gpkg", layer="final_open_land_zones")
    engine = LandingZoneEngine()
    holes = [(i, g) for i, g in enumerate(zones.geometry) if g.geom_type == "Polygon" and len(g.interiors)]
    result = {
        "dataset": str(imagery / "bhadra_final_open_land_zones.gpkg"),
        "zones": len(zones), "area_km2": float(zones.area.sum() / 1e6),
        "crs": str(zones.crs), "valid_geometries": bool(zones.is_valid.all()),
        "engine_zones": engine.total_zones, "zones_with_holes": len(holes),
        "total_holes": sum(len(g.interiors) for _, g in holes),
        "excluded_hole_area_m2": sum(Polygon(r).area for _, g in holes for r in g.interiors),
        "osm_layers": gpd.list_layers(base / "osm/bhadra_osm_context.gpkg").to_dict(orient="records"),
    }
    buildings = gpd.read_file(base / "osm/bhadra_osm_context.gpkg", layer="buildings").to_crs(zones.crs)
    overture = gpd.read_file(base / "buildings/bhadra_overture_buildings.geojson").to_crs(zones.crs)
    result["building_source_counts"] = {"osm": len(buildings), "overture": len(overture)}
    from shapely import union_all
    building_union = union_all([*buildings.geometry, *overture.geometry])
    result["building_overlap_m2"] = float(zones.intersection(building_union).area.sum())
    idx = zones.sindex
    pairs = idx.query(zones.geometry, predicate="intersects")
    result["zone_overlap_pairs_above_1e_6_m2"] = sum(
        zones.geometry.iloc[i].intersection(zones.geometry.iloc[j]).area > 1e-6
        for i, j in zip(*pairs) if i < j
    )
    b = _read_inputs(imagery / "bhadra_spectral.tif", imagery / "bhadra_scl.tif")
    state = apply_cloud_edge_buffer(classify_open_pixels(
        b[6], safe_normalized_difference(b[3], b[2]), safe_normalized_difference(b[1], b[4])
    ), b[6], 3)
    mask = rasterize([(g, 1) for g in zones.geometry], out_shape=state.shape,
                     transform=b[7]["transform"], dtype="uint8")
    values, counts = np.unique(state, return_counts=True)
    result["reclassified_state_counts_full_grid"] = {int(v): int(c) for v, c in zip(values, counts)}
    result["zone_pixel_centers"] = {
        "unknown": int(np.count_nonzero((mask == 1) & (state == 255))),
        "not_open": int(np.count_nonzero((mask == 1) & (state == 0))),
        "scl_water": int(np.count_nonzero((mask == 1) & (b[6] == 6))),
    }
    if holes:
        i, actual = holes[0]
        zone_id = zones.iloc[i].zone_id
        entry = next(z for z in engine.zones if z["zone_id"] == zone_id)
        displayed = Polygon([(pt[1], pt[0]) for pt in entry["polygon"]])
        displayed = gpd.GeoSeries([displayed], crs=4326).to_crs(zones.crs).iloc[0]
        result["display_reproduction"] = {
            "zone_id": zone_id, "actual_holes": len(actual.interiors),
            "displayed_holes": len(displayed.interiors),
            "extra_display_area_m2": float(displayed.difference(actual).area),
            "missing_display_area_m2": float(actual.difference(displayed).area),
        }
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(1, 2, figsize=(10, 5), constrained_layout=True)
        for ax, geom, title in zip(axes, [actual, displayed], ["Stored candidate: hole preserved", "Current map export: hole filled"]):
            gpd.GeoSeries([geom], crs=zones.crs).plot(ax=ax, color="#79c9a1", edgecolor="#175638")
            gpd.GeoSeries([Polygon(r) for r in actual.interiors], crs=zones.crs).boundary.plot(ax=ax, color="#d13737", linewidth=2)
            ax.set_aspect("equal")
            ax.set_title(title)
            ax.ticklabel_format(useOffset=False, style="plain")
            ax.set_xlabel("UTM easting (m)")
            ax.set_ylabel("UTM northing (m)")
        fig.suptitle(f"{zone_id}: red outline marks excluded interior")
        fig.savefig(OUT / "polygon-hole-reproduction.png", dpi=150)
        plt.close(fig)
    (OUT / "audit-evidence.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
