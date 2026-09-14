import sqlite3
import json
import math
from pathlib import Path

def inspect():
    root = Path(r"c:\Users\Nehar\Desktop\HELPS\Codes")
    gpkg = root / "data" / "processed" / "Bhadra" / "sentinel2" / "2026-06-01" / "bhadra_final_open_land_zones.gpkg"
    if gpkg.exists():
        conn = sqlite3.connect(str(gpkg))
        c = conn.cursor()
        c.execute("SELECT table_name, data_type FROM gpkg_contents")
        print("gpkg_contents:", c.fetchall())
        c.execute("PRAGMA table_info(final_open_land_zones)")
        cols = c.fetchall()
        print("Columns in final_open_land_zones:", [col[1] for col in cols])
        c.execute("SELECT count(*) FROM final_open_land_zones")
        print("Count:", c.fetchone()[0])
        c.execute("SELECT zone_id, parent_candidate_id, area_m2, length_m, width_m, max_clear_diameter_m FROM final_open_land_zones LIMIT 10")
        for r in c.fetchall():
            print("Zone sample:", r)
        
        # Check spatial ref / srs
        c.execute("SELECT * FROM gpkg_spatial_ref_sys")
        print("Spatial refs:", c.fetchall())
        
        # Check geometry header / coordinates sample
        c.execute("SELECT hex(substr(geom, 1, 64)) FROM final_open_land_zones LIMIT 2")
        print("Geom hex headers:", c.fetchall())

    geojson_path = root / "data" / "raw" / "Bhadra" / "bhadra_entire_region.geojson"
    if geojson_path.exists():
        with open(geojson_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            print("Raw Bhadra geojson keys / feature count:", len(data.get("features", [])))
            if data.get("features"):
                print("First feature properties:", data["features"][0].get("properties"))
                print("Geometry type:", data["features"][0].get("geometry", {}).get("type"))
                coords = data["features"][0].get("geometry", {}).get("coordinates")
                print("Sample coord:", coords[0][0] if coords else None)

    runs_dir = root / "data" / "runs"
    if runs_dir.exists():
        print("Runs dirs:", list(runs_dir.iterdir()))

if __name__ == "__main__":
    inspect()
