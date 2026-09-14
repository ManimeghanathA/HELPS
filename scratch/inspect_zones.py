import sqlite3
import struct
import math
from pathlib import Path

def inspect_all():
    gpkg = Path(r"c:\Users\Nehar\Desktop\HELPS\Codes\data\processed\Bhadra\sentinel2\2026-06-01\bhadra_final_open_land_zones.gpkg")
    conn = sqlite3.connect(str(gpkg))
    c = conn.cursor()
    
    # Query final_open_land_zones joined with maximum_clearance_centers if needed, or query both
    c.execute("""
        SELECT f.fid, f.zone_id, f.parent_candidate_id, f.area_m2, f.length_m, f.width_m, f.max_clear_diameter_m,
               m.geom
        FROM final_open_land_zones f
        LEFT JOIN maximum_clearance_centers m ON f.parent_candidate_id = m.parent_candidate_id AND f.zone_number = m.zone_number
        LIMIT 10
    """)
    rows = c.fetchall()
    print("Joined rows sample count:", len(rows))
    for r in rows:
        fid, zone_id, parent_id, area, length, width, clear_dia, blob = r
        print(f"Zone: {zone_id}, Area: {area:.1f} m2, {length:.1f}x{width:.1f}m, ClearDia: {clear_dia:.1f}m, HasGeom: {blob is not None}")

if __name__ == "__main__":
    inspect_all()
